"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [backendOnline, setBackendOnline] = useState(false);
  const [researchTask, setResearchTask] = useState("");
  const [researchResult, setResearchResult] = useState("");
  const [researchRunning, setResearchRunning] = useState(false);

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await fetch("http://localhost:8000/health");

        if (response.ok) {
          setBackendOnline(true);
        } else {
          setBackendOnline(false);
        }
      } catch {
        setBackendOnline(false);
      }
    };

    checkBackend();

    const interval = setInterval(checkBackend, 5000);

    return () => clearInterval(interval);
  }, []);

  const runResearchAgent = async () => {
    if (!researchTask.trim()) {
      return;
    }

    setResearchRunning(true);
    setResearchResult("");

    try {
      const response = await fetch(
        "http://localhost:8000/agents/research/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task: researchTask.trim() }),
        }
      );

      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Opgaven skal indeholde 1–10.000 tegn.");
      }

      setResearchResult(data.response);
    } catch (error) {
      setResearchResult(error instanceof Error && !(error instanceof TypeError) ? error.message : "Kunne ikke forbinde til Research Agent.");
    } finally {
      setResearchRunning(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-7xl px-8 py-10">
        {/* Header */}
        <header className="mb-12 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.25em] text-blue-400">
              Alexander&apos;s AI Platform
            </p>

            <h1 className="mt-2 text-4xl font-bold tracking-tight">
              AI Control Center
            </h1>

            <p className="mt-2 text-zinc-400">
              Private AI agent platform
            </p>
          </div>

          <div
            className={`rounded-full border px-4 py-2 text-sm ${
              backendOnline
                ? "border-green-500/30 bg-green-500/10 text-green-400"
                : "border-red-500/30 bg-red-500/10 text-red-400"
            }`}
          >
            ● {backendOnline ? "System Online" : "System Offline"}
          </div>
        </header>

        {/* System status */}
        <section className="mb-12">
          <h2 className="mb-5 text-xl font-semibold">System Status</h2>

          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            <StatusCard
              title="Backend"
              value="FastAPI"
              status={backendOnline ? "Online" : "Offline"}
              online={backendOnline}
            />

            <StatusCard
              title="Frontend"
              value="Next.js"
              status="Online"
              online={true}
            />

            <StatusCard
              title="Agents"
              value="1 Active"
              status="Ready"
              online={true}
            />

            <StatusCard
              title="Version"
              value="v0.2.0"
              status="Development"
              online={true}
            />
          </div>
        </section>

        {/* Agents */}
        <section>
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">AI Agents</h2>

              <p className="mt-1 text-sm text-zinc-500">
                Specialized agents connected to your AI Control Center
              </p>
            </div>

            <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium transition hover:bg-blue-500">
              + New Agent
            </button>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            {/* Research Agent */}
            <div className="rounded-xl border border-blue-500/30 bg-zinc-900 p-6 lg:col-span-2">
              <div className="mb-5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
                    AI
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold">
                      Research Agent
                    </h3>

                    <p className="text-sm text-zinc-500">
                      Bruger Codex/ChatGPT. Henter ikke aktuelle oplysninger fra internettet.
                    </p>
                  </div>
                </div>

                <span className="text-xs text-green-400">
                  ● Ready
                </span>
              </div>

              <textarea
                maxLength={10000}
                value={researchTask}
                onChange={(event) => setResearchTask(event.target.value)}
                placeholder="Give Research Agent a task, e.g. Analyze Netflix..."
                className="min-h-28 w-full resize-none rounded-lg border border-zinc-700 bg-zinc-950 p-4 text-sm text-white outline-none transition placeholder:text-zinc-600 focus:border-blue-500"
              />

              <div className="mt-4 flex items-center justify-between">
                <p className="text-xs text-zinc-500">
                  Codex/ChatGPT via lokal FastAPI
                </p>

                <button
                  onClick={runResearchAgent}
                  disabled={
                    researchRunning ||
                    !researchTask.trim() ||
                    !backendOnline
                  }
                  className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {researchRunning ? "Running..." : "Run Agent"}
                </button>
              </div>

              {researchResult && (
                <div className="mt-5 rounded-lg border border-zinc-800 bg-zinc-950 p-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
                    Agent Response
                  </p>

                  <p className="whitespace-pre-wrap break-words text-sm leading-6 text-zinc-300">
                    {researchResult}
                  </p>
                </div>
              )}
            </div>

            {/* Other agents */}
            <div className="space-y-5">
              <AgentCard
                name="Market Analyst"
                description="Analyzes stocks, markets and financial data."
              />

              <AgentCard
                name="Options Specialist"
                description="Evaluates options strategies, risk and opportunities."
              />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function StatusCard({
  title,
  value,
  status,
  online,
}: {
  title: string;
  value: string;
  status: string;
  online: boolean;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <p className="text-sm text-zinc-500">{title}</p>

      <p className="mt-2 text-xl font-semibold">{value}</p>

      <p
        className={`mt-3 text-sm ${
          online ? "text-green-400" : "text-red-400"
        }`}
      >
        ● {status}
      </p>
    </div>
  );
}

function AgentCard({
  name,
  description,
}: {
  name: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 transition hover:border-zinc-700">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
          AI
        </div>

        <span className="text-xs text-zinc-500">
          Not configured
        </span>
      </div>

      <h3 className="text-lg font-semibold">{name}</h3>

      <p className="mt-2 text-sm leading-6 text-zinc-400">
        {description}
      </p>

      <button className="mt-6 text-sm font-medium text-blue-400 hover:text-blue-300">
        Configure →
      </button>
    </div>
  );
}