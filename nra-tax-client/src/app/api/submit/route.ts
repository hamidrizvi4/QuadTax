import { NextRequest, NextResponse } from 'next/server';

// Server-side proxy for the tax engine's /submit endpoint.
//
// The engine API key lives ONLY here (server-side env), never in the browser
// bundle. The client calls this same-origin route; we forward to the engine
// with the Bearer key attached.

const ENGINE_URL =
  process.env.QUADTAX_ENGINE_URL ?? 'http://localhost:8000/api/v1';
const API_KEY = process.env.QUADTAX_API_KEY;

export async function POST(req: NextRequest) {
  if (!API_KEY) {
    return NextResponse.json(
      { detail: 'Server auth not configured' },
      { status: 503 },
    );
  }

  const upstream = await fetch(`${ENGINE_URL}/submit`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`,
    },
    body: await req.text(),
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
