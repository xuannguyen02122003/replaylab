import type { Issue } from "../types/api";

/** Shown when a trace is incomplete, so partial data is never mistaken for a full run. */
export function IssuesBanner({ issues }: { issues: Issue[] }) {
  if (issues.length === 0) return null;
  return (
    <div role="alert" className="rounded-lg border border-dashed border-warn bg-warn-soft px-4 py-3 text-sm">
      <p className="font-semibold text-warn">This trace is incomplete. What you see may not be the whole run.</p>
      <ul className="mt-1 list-disc pl-5">
        {issues.map((issue) => (
          <li key={issue.code}>{issue.message}</li>
        ))}
      </ul>
    </div>
  );
}
