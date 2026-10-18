import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Agents (writer_agent especially) return markdown-formatted text. This
// renders it with dark-theme-appropriate styling instead of showing raw
// "##"/"**" syntax.
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="text-slate-200 leading-relaxed [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => <h1 className="text-xl font-bold text-slate-100 mt-5 mb-2" {...props} />,
          h2: (props) => <h2 className="text-lg font-bold text-slate-100 mt-5 mb-2" {...props} />,
          h3: (props) => <h3 className="text-base font-semibold text-slate-100 mt-4 mb-2" {...props} />,
          p: (props) => <p className="text-sm text-slate-300 mb-3" {...props} />,
          ul: (props) => <ul className="list-disc list-inside text-sm text-slate-300 mb-3 space-y-1" {...props} />,
          ol: (props) => <ol className="list-decimal list-inside text-sm text-slate-300 mb-3 space-y-1" {...props} />,
          li: (props) => <li className="text-sm text-slate-300" {...props} />,
          strong: (props) => <strong className="font-semibold text-slate-100" {...props} />,
          a: (props) => <a className="text-blue-300 hover:text-blue-200 underline" target="_blank" rel="noopener noreferrer" {...props} />,
          code: (props) => <code className="px-1 py-0.5 rounded bg-white/10 text-emerald-300 text-xs" {...props} />,
          blockquote: (props) => <blockquote className="border-l-2 border-white/20 pl-3 text-slate-400 italic" {...props} />,
          hr: () => <hr className="border-white/10 my-4" />,
          table: (props) => <table className="w-full text-sm text-slate-300 border-collapse mb-3" {...props} />,
          th: (props) => <th className="text-left text-slate-100 border-b border-white/20 px-2 py-1" {...props} />,
          td: (props) => <td className="border-b border-white/10 px-2 py-1" {...props} />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
