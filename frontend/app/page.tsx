"use client";

import { useRef, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production"
    ? "https://resume-backendd.onrender.com"
    : "http://localhost:8000");
const MAX_FILE_BYTES = 5 * 1024 * 1024;
const MIN_JD = 50;
const MAX_JD = 15000;

type Experience = {
  title: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  bullets: string[];
};
type Education = {
  degree: string;
  institution: string;
  year: string;
  details: string;
};
type Project = { name: string; description: string; bullets: string[] };
type Resume = {
  name: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  summary: string;
  skills: string[];
  experience: Experience[];
  projects: Project[];
  education: Education[];
  certifications: string[];
};
type Result = { resume: Resume; changes: string[]; match_keywords: string[] };

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return "Please check your inputs and try again.";
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status}).`;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [jd, setJd] = useState("");
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState<"pdf" | "docx" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function pickFile(f: File | null) {
    setError(null);
    if (!f) return setFile(null);
    if (!/\.(pdf|docx)$/i.test(f.name)) {
      setFile(null);
      return setError("Please upload a .pdf or .docx file.");
    }
    if (f.size > MAX_FILE_BYTES) {
      setFile(null);
      return setError("File is too large (max 5 MB).");
    }
    setFile(f);
  }

  const jdLen = jd.trim().length;
  const canSubmit =
    !!file && jdLen >= MIN_JD && jdLen <= MAX_JD && !loading;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("resume", file);
      form.append("job_description", jd.trim());
      const res = await fetch(`${API_URL}/customize`, {
        method: "POST",
        body: form,
        signal: AbortSignal.timeout(120_000),
      });
      if (!res.ok) throw new Error(await errorMessage(res));
      setResult(await res.json());
    } catch (err) {
      if (err instanceof DOMException && err.name === "TimeoutError") {
        setError("This is taking too long. Please try again.");
      } else if (err instanceof TypeError) {
        setError("Cannot reach the server. Is the backend running?");
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function onDownload(format: "pdf" | "docx") {
    if (!result) return;
    setDownloading(format);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/download?format=${format}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(result.resume),
      });
      if (!res.ok) throw new Error(await errorMessage(res));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${result.resume.name.replace(/\W+/g, "_") || "resume"}_Resume.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Resume Customizer</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Upload your resume, paste a job description, and get a version
          tailored to the role. Only facts from your resume are used.
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-6">
        <div>
          <label className="mb-2 block text-sm font-medium">1. Your resume (PDF or DOCX)</label>
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              pickFile(e.dataTransfer.files?.[0] ?? null);
            }}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${
              dragging
                ? "border-blue-500 bg-blue-500/10"
                : "border-zinc-300 hover:border-zinc-400 dark:border-zinc-700"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <p className="font-medium">
                {file.name}{" "}
                <span className="font-normal text-zinc-500">
                  ({(file.size / 1024).toFixed(0)} KB) - click to change
                </span>
              </p>
            ) : (
              <p className="text-zinc-600 dark:text-zinc-400">
                Drag a file here or click to browse (max 5 MB)
              </p>
            )}
          </div>
        </div>

        <div>
          <label htmlFor="jd" className="mb-2 block text-sm font-medium">
            2. Job description
          </label>
          <textarea
            id="jd"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            rows={10}
            placeholder="Paste the full job posting here..."
            className="w-full rounded-lg border border-zinc-300 bg-transparent p-3 text-sm outline-none focus:border-blue-500 dark:border-zinc-700"
          />
          <p
            className={`mt-1 text-xs ${
              jdLen > MAX_JD || (jdLen > 0 && jdLen < MIN_JD)
                ? "text-red-500"
                : "text-zinc-500"
            }`}
          >
            {jdLen.toLocaleString()} / {MAX_JD.toLocaleString()} characters (min {MIN_JD})
          </p>
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading && (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          )}
          {loading ? "Tailoring your resume..." : "Customize my resume"}
        </button>
        {loading && (
          <p className="text-sm text-zinc-500">This usually takes 10-30 seconds.</p>
        )}
      </form>

      {error && (
        <div
          role="alert"
          className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-600 dark:text-red-400"
        >
          {error}
        </div>
      )}

      {result && (
        <section className="mt-10 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl font-semibold">Your tailored resume</h2>
            <div className="flex gap-2">
              {(["pdf", "docx"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => onDownload(f)}
                  disabled={downloading !== null}
                  className="h-10 rounded-lg border border-zinc-300 px-4 text-sm font-medium transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
                >
                  {downloading === f ? "Preparing..." : `Download ${f.toUpperCase()}`}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
              <h3 className="mb-2 font-medium">What changed</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {result.changes.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg border border-zinc-300 p-4 dark:border-zinc-700">
              <h3 className="mb-2 font-medium">Matched keywords</h3>
              <div className="flex flex-wrap gap-2">
                {result.match_keywords.map((k, i) => (
                  <span
                    key={i}
                    className="rounded-full bg-green-500/15 px-2.5 py-1 text-xs text-green-700 dark:text-green-400"
                  >
                    {k}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <ResumePreview r={result.resume} />
        </section>
      )}
    </main>
  );
}

function H({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 mt-6 border-b border-zinc-300 pb-1 text-sm font-semibold uppercase tracking-wide dark:border-zinc-700">
      {children}
    </h3>
  );
}

function ResumePreview({ r }: { r: Resume }) {
  const contact = [r.email, r.phone, r.location, ...r.links].filter(Boolean);
  return (
    <article className="rounded-lg border border-zinc-300 bg-white p-6 text-sm text-zinc-900 shadow-sm sm:p-8">
      <h2 className="text-2xl font-bold">{r.name}</h2>
      {contact.length > 0 && (
        <p className="mt-1 text-zinc-600">{contact.join("  |  ")}</p>
      )}

      {r.summary && (
        <>
          <H>Summary</H>
          <p>{r.summary}</p>
        </>
      )}
      {r.skills.length > 0 && (
        <>
          <H>Skills</H>
          <p>{r.skills.join(", ")}</p>
        </>
      )}
      {r.experience.length > 0 && (
        <>
          <H>Experience</H>
          {r.experience.map((e, i) => (
            <div key={i} className="mb-3">
              <p className="font-semibold">
                {e.title} - {e.company}
              </p>
              <p className="text-xs text-zinc-500">
                {[e.location, [e.start_date, e.end_date].filter(Boolean).join(" - ")]
                  .filter(Boolean)
                  .join("  |  ")}
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {e.bullets.map((b, j) => (
                  <li key={j}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
      {r.projects.length > 0 && (
        <>
          <H>Projects</H>
          {r.projects.map((p, i) => (
            <div key={i} className="mb-3">
              <p className="font-semibold">{p.name}</p>
              {p.description && <p>{p.description}</p>}
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {p.bullets.map((b, j) => (
                  <li key={j}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
      {r.education.length > 0 && (
        <>
          <H>Education</H>
          {r.education.map((e, i) => (
            <div key={i} className="mb-2">
              <p className="font-semibold">
                {e.degree} - {e.institution}
              </p>
              <p className="text-xs text-zinc-500">
                {[e.year, e.details].filter(Boolean).join("  |  ")}
              </p>
            </div>
          ))}
        </>
      )}
      {r.certifications.length > 0 && (
        <>
          <H>Certifications</H>
          <ul className="list-disc pl-5">
            {r.certifications.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}
