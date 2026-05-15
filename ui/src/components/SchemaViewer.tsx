/**
 * Author: Sarala Biswal
 */
import CodeBlock from "./CodeBlock";

interface SchemaViewerProps {
  title: string;
  schema: Record<string, unknown>;
}

/**
 * Renders structured schema examples for implementation reference.
 */
export default function SchemaViewer({ title, schema }: SchemaViewerProps): JSX.Element {
  return (
    <section className="rounded-md border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-100">{title}</h2>
      <CodeBlock code={JSON.stringify(schema, null, 2)} language="json" />
    </section>
  );
}
