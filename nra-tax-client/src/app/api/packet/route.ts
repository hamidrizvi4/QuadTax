import { NextRequest, NextResponse } from 'next/server';

// Server-side proxy for the tax engine's /packet endpoint.
//
// The engine API key lives ONLY here (server-side env), never in the browser
// bundle. The path query param is forwarded verbatim — FastAPI's own
// path-traversal guard still applies upstream.

const ENGINE_URL =
  process.env.QUADTAX_ENGINE_URL ?? 'http://localhost:8000/api/v1';
const API_KEY = process.env.QUADTAX_API_KEY;

export async function GET(req: NextRequest) {
  if (!API_KEY) {
    return NextResponse.json(
      { detail: 'Server auth not configured' },
      { status: 503 },
    );
  }

  const path = req.nextUrl.searchParams.get('path') ?? '';

  const upstream = await fetch(
    `${ENGINE_URL}/packet?path=${encodeURIComponent(path)}`,
    {
      method: 'GET',
      headers: { Authorization: `Bearer ${API_KEY}` },
    },
  );

  if (!upstream.ok) {
    return NextResponse.json(
      { detail: 'Packet not available' },
      { status: upstream.status },
    );
  }

  const blob = await upstream.blob();
  return new NextResponse(blob, {
    status: 200,
    headers: { 'Content-Type': 'application/pdf' },
  });
}
