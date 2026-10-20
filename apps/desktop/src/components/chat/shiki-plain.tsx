/** Matches highlighted markup so loading a grammar changes color, not layout. */
export function PlainShiki({ code }: { code: string }) {
  return (
    <div className="rs-root not-prose">
      <pre className="shiki whitespace-pre-wrap wrap-anywhere" style={{ backgroundColor: 'transparent', margin: 0, overflowX: 'hidden', maxWidth: '100%' }}>
        <code className="block whitespace-pre-wrap wrap-anywhere">{code}</code>
      </pre>
    </div>
  )
}
