import shutil
from pathlib import Path

from pyspark.sql import SparkSession

spark = (
    SparkSession.builder.master("local[1]")
    .appName("resolve-kafka-connector")
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.4")
    .config("spark.jars.repositories", "https://repo.maven.apache.org/maven2")
    .config("spark.ui.enabled", "false")
    .getOrCreate()
)
spark.stop()
out = Path("/opt/kafka-jars")
out.mkdir(exist_ok=True)
for folder in [Path.home() / ".ivy2/jars", Path.home() / ".ivy2.5.2/jars"]:
    if folder.exists():
        for path in folder.glob("*.jar"):
            shutil.copy2(path, out / path.name)
if not list(out.glob("*spark-sql-kafka*")):
    raise RuntimeError("Matched Kafka connector was not resolved")
