import { useRef, useState } from "react";

import { importCopy } from "./importCopy";
import type { Locale } from "./types";

export function ImportUploader({
  locale,
  busy,
  error,
  onUpload,
}: {
  locale: Locale;
  busy: boolean;
  error: string | null;
  onUpload: (file: File) => void;
}) {
  const t = importCopy[locale];
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function selectFile(candidate: File | undefined) {
    if (!candidate) return;
    if (!candidate.name.toLocaleLowerCase().endsWith(".xlsx")) {
      setFile(null);
      setFileError(t.unsupportedFile);
      return;
    }
    setFile(candidate);
    setFileError(null);
  }

  return (
    <section
      className={`panel import-uploader${dragging ? " import-uploader-active" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        selectFile(event.dataTransfer.files.item(0) ?? undefined);
      }}
    >
      <div className="import-upload-icon" aria-hidden="true">⇧</div>
      <div>
        <h2>{t.uploadTitle}</h2>
        <p>{t.uploadHelp}</p>
      </div>
      <div className="import-drop-label">{t.dropHelp}</div>
      <input
        ref={inputRef}
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        aria-label={t.chooseFile}
        className="visually-hidden"
        disabled={busy}
        onChange={(event) => selectFile(event.currentTarget.files?.item(0) ?? undefined)}
        type="file"
      />
      <div className="import-upload-actions">
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          type="button"
        >
          {t.chooseFile}
        </button>
        {file && <span className="import-selected-file" title={file.name}>{file.name}</span>}
        <button
          className="primary-button"
          disabled={!file || busy}
          onClick={() => file && onUpload(file)}
          type="button"
        >
          {busy ? t.uploading : t.uploadSelected}
        </button>
      </div>
      {(fileError || error) && <p className="table-error" role="alert">{fileError ?? error}</p>}
    </section>
  );
}
