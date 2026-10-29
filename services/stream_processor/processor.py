"""Two bounded Structured Streaming queries per replay, each with durable checkpoints."""

from pathlib import Path

from marketpulse.config import BROKERS, CURATED, DATA, RAW
from services.ingestor.kafka_io import flush_outbox
from services.warehouse_loader.postgres import audit_batch, save_progress, window_batch


def spark_session():
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName("MarketPulse-event-time")
        .master("local[2]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "3")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.memory", "1g")
        .config("spark.sql.streaming.noDataMicroBatches.enabled", "true")
        .config("spark.sql.streaming.stateStore.maintenanceInterval", "10s")
        .config("spark.jars", ",".join(str(p) for p in Path("/opt/kafka-jars").glob("*.jar")))
        .getOrCreate()
    )


def source(spark, topic: str, run_id: str, offsets: str = "earliest"):
    from pyspark.sql import functions as F

    frame = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", BROKERS)
        .option("subscribe", topic)
        .option("startingOffsets", offsets)
        .option("maxOffsetsPerTrigger", 600)
        .option("failOnDataLoss", "true")
        .load()
        .selectExpr("CAST(value AS STRING) value", "topic", "partition", "offset")
    )
    return frame if topic == RAW else frame.filter(F.get_json_object("value", "$.run_id") == run_id)


def process(run: dict) -> None:
    from pyspark.sql import functions as F
    from pyspark.sql import types as T

    run_id = str(run["id"])
    checkpoint = DATA / "checkpoints" / run_id
    checkpoint.mkdir(parents=True, exist_ok=True)
    spark = spark_session()
    spark.sparkContext.setLogLevel("WARN")

    def raw_sink(df, batch_id):
        audit_batch(run_id, int(batch_id), [r.asDict(recursive=True) for r in df.toLocalIterator()])
        flush_outbox(run_id)

    try:
        raw = source(spark, RAW, run_id, run["config"].get("raw_offsets", "earliest"))
        q = (
            raw.writeStream.foreachBatch(raw_sink)
            .option("checkpointLocation", str(checkpoint / "raw"))
            .trigger(availableNow=True)
            .start()
        )
        q.awaitTermination(900)
        if q.isActive:
            q.stop()
            raise TimeoutError("Raw query exceeded its local run budget")
        for p in q.recentProgress:
            save_progress(run_id, "raw", p)
        flush_outbox(run_id)
        # Keep decimal prices/volumes in Spark and PostgreSQL. No binary floating-point money arithmetic.
        schema = T.StructType(
            [
                T.StructField("run_id", T.StringType()),
                T.StructField(
                    "event",
                    T.StructType(
                        [
                            T.StructField("event_id", T.StringType()),
                            T.StructField("symbol", T.StringType()),
                            T.StructField("event_time_utc", T.StringType()),
                            *[
                                T.StructField(name, T.StringType())
                                for name in ["price", "open", "high", "low", "volume"]
                            ],
                        ]
                    ),
                ),
            ]
        )
        parsed = (
            source(spark, CURATED, run_id, run["config"].get("curated_offsets", "earliest"))
            .select(F.from_json("value", schema).alias("p"))
            .select("p.run_id", "p.event.*")
            .withColumn("event_time", F.to_timestamp("event_time_utc"))
        )
        for name in ["price", "open", "high", "low", "volume"]:
            parsed = parsed.withColumn(name, F.col(name).cast(T.DecimalType(28, 12)))
        windowed = (
            parsed.withWatermark("event_time", f"{run['watermark_minutes']} minutes")
            .groupBy("run_id", "symbol", F.window("event_time", f"{run['window_minutes']} minutes"))
            .agg(
                F.collect_set(
                    F.struct("event_id", "event_time", "price", "open", "high", "low", "volume")
                ).alias("events")
            )
        )

        def window_sink(df, batch_id):
            failed = window_batch(
                run_id, int(batch_id), [r.asDict(recursive=True) for r in df.toLocalIterator()]
            )
            if failed:
                raise RuntimeError(
                    "Local reliability experiment: sink committed, checkpoint acknowledgement interrupted"
                )

        for attempt in range(2):
            try:
                q = (
                    windowed.writeStream.outputMode("update")
                    .foreachBatch(window_sink)
                    .option("checkpointLocation", str(checkpoint / "windows"))
                    .trigger(availableNow=True)
                    .start()
                )
                q.awaitTermination(900)
                if q.isActive:
                    q.stop()
                    raise TimeoutError("Window query exceeded its local run budget")
                for p in q.recentProgress:
                    save_progress(run_id, "windows", p)
                break
            except Exception:
                if attempt or run["scenario"] not in ("restart", "warehouse_retry"):
                    raise
                # Reconstruct the same query with the same checkpoint. Sink ledger makes the retried batch a no-op.
                if q.isActive:
                    q.stop()
    finally:
        spark.stop()
