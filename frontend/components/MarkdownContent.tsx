"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Components } from "react-markdown";

const codeStyle: React.CSSProperties = {
  margin: 0,
  borderRadius: "0.5rem",
  fontSize: "0.75rem",
  lineHeight: "1.6",
  background: "#050508",
};

const components: Components = {
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    const isInline = !match && !className;
    if (isInline) {
      return (
        <code
          className="px-1.5 py-0.5 rounded text-xs font-mono bg-[#050508] text-axon-cyan border border-axon-border"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <SyntaxHighlighter
        style={oneDark}
        language={match?.[1] ?? "text"}
        PreTag="div"
        customStyle={codeStyle}
      >
        {String(children).replace(/\n$/, "")}
      </SyntaxHighlighter>
    );
  },
  pre({ children }) {
    return (
      <div className="my-3 rounded-xl border border-axon-border overflow-hidden">
        {children}
      </div>
    );
  },
  p({ children }) {
    return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
  },
  ul({ children }) {
    return <ul className="mb-2 pl-4 space-y-1 list-disc list-outside">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="mb-2 pl-4 space-y-1 list-decimal list-outside">{children}</ol>;
  },
  li({ children }) {
    return <li className="leading-relaxed">{children}</li>;
  },
  h1({ children }) {
    return <h1 className="text-base font-bold mb-2 text-axon-text">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="text-sm font-bold mb-1.5 text-axon-text">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="text-sm font-semibold mb-1 text-axon-text">{children}</h3>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-axon-cyan pl-3 my-2 text-axon-muted italic">
        {children}
      </blockquote>
    );
  },
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-axon-cyan underline underline-offset-2 hover:opacity-80">
        {children}
      </a>
    );
  },
  strong({ children }) {
    return <strong className="font-semibold text-axon-text">{children}</strong>;
  },
  hr() {
    return <hr className="my-3 border-axon-border" />;
  },
};

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
