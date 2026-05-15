/**
 * Author: Sarala Biswal
 */
interface CodeBlockProps {
  code: string;
  language?: "json" | "python" | "text";
}

/**
 * Renders formatted code or JSON payloads for audit and architecture details.
 */
export default function CodeBlock({ code, language = "text" }: CodeBlockProps): JSX.Element {
  return (
    <pre className="overflow-x-auto rounded-md border border-slate-800 bg-slate-950 p-4 text-xs leading-6 text-slate-200">
      <code data-language={language}>{code}</code>
    </pre>
  );
}
