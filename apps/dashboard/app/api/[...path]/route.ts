import { NextRequest, NextResponse } from "next/server";
const allowed = new Set([
  "health",
  "overview",
  "series",
  "windows",
  "operations",
  "runs",
  "catalog",
  "lab/replays",
]);
async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const endpoint = path.join("/");
  if (!allowed.has(endpoint))
    return NextResponse.json(
      { detail: "Unknown API resource" },
      { status: 404 },
    );
  if (request.method === "POST") {
    if (endpoint !== "lab/replays")
      return NextResponse.json(
        { detail: "Read-only resource" },
        { status: 405 },
      );
    const origin = request.headers.get("origin");
    const allowedOrigins = (
      process.env.MP_DASHBOARD_ORIGINS ||
      "http://127.0.0.1:8031,http://localhost:8031"
    ).split(",");
    if (origin && !allowedOrigins.includes(origin))
      return NextResponse.json(
        { detail: "Cross-origin lab requests are not accepted" },
        { status: 403 },
      );
    if (Number(request.headers.get("content-length") || 0) > 4096)
      return NextResponse.json(
        { detail: "Request is too large" },
        { status: 413 },
      );
  }
  try {
    const base = process.env.API_INTERNAL_URL || "http://127.0.0.1:8030";
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 4096)
      return NextResponse.json(
        { detail: "Request is too large" },
        { status: 413 },
      );
    const upstream = await fetch(
      `${base}/${endpoint === "health" ? "health" : "api/" + endpoint}${request.nextUrl.search}`,
      {
        method: request.method,
        headers: { "Content-Type": "application/json" },
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
      },
    );
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "The API is unavailable. Check that the local MarketPulse services are running.",
      },
      { status: 503 },
    );
  }
}
export const GET = forward;
export const POST = forward;
