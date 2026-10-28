#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/../frontend" && pwd)"

echo "🚀 Starting ProbeBench React Studio..."
cd "${FRONTEND_DIR}"

if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm dependencies..."
    npm install
fi

echo "🌐 Launching Vite development server at http://localhost:3000 ..."
npm run dev -- --host

