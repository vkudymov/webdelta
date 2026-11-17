"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "../hooks/useTranslation";
import { helpContent } from "../i18n/help";

function Block({ block }) {
  if (block.type === "p") {
    return <p className="text-sm text-gray-700 leading-relaxed">{block.text}</p>;
  }
  if (block.type === "note") {
    return (
      <p className="text-sm text-amber-900 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2 leading-relaxed">
        {block.text}
      </p>
    );
  }
  if (block.type === "ul") {
    return (
      <ul className="list-disc pl-5 space-y-1.5 text-sm text-gray-700 leading-relaxed">
        {block.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  }
  if (block.type === "steps") {
    return (
      <ol className="list-decimal pl-5 space-y-2 text-sm text-gray-700 leading-relaxed">
        {block.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ol>
    );
  }
  return null;
}

export default function HelpDialog({ onClose }) {
  const { t, locale } = useTranslation();
  const content = helpContent[locale] || helpContent.ru;
  const bodyRef = useRef(null);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const dialog = (
    <div
      className="fixed inset-0 bg-black/50 flex items-start justify-center z-[100] p-4 overflow-y-auto"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-dialog-title"
        className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full my-8 flex flex-col max-h-[min(90vh,880px)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 px-6 py-4 border-b shrink-0">
          <div>
            <h2 id="help-dialog-title" className="text-xl font-semibold text-gray-800">
              {content.title}
            </h2>
            <p className="text-sm text-blue-800 font-medium mt-1">{content.leadTitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-xl text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200"
          >
            {t("close")}
          </button>
        </div>

        <div ref={bodyRef} className="overflow-y-auto px-6 py-5 space-y-8">
          <div className="space-y-2">
            {content.lead.map((paragraph) => (
              <p key={paragraph} className="text-[15px] text-gray-800 leading-relaxed">
                {paragraph}
              </p>
            ))}
          </div>

          <nav className="flex flex-wrap gap-2">
            {content.sections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() => {
                  const node = bodyRef.current?.querySelector(`[data-help-section="${section.id}"]`);
                  node?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
                className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-blue-50 hover:text-blue-800"
              >
                {section.title}
              </button>
            ))}
          </nav>

          {content.sections.map((section) => (
            <section key={section.id} data-help-section={section.id} className="scroll-mt-4 space-y-3">
              <h3 className="text-base font-semibold text-gray-900">{section.title}</h3>
              {section.blocks.map((block, index) => (
                <Block key={`${section.id}-${index}`} block={block} />
              ))}
            </section>
          ))}
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(dialog, document.body);
}
