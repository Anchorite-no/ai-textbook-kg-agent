/** 拖拽上传区。plan 16 §11.2。
 *  - 拖拽 + 点击上传
 *  - 支持 PDF / Word / Excel / PPT
 *  - 多文件批量上传
 *  - 上传进度显示 */

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, AlertCircle, Loader2 } from "lucide-react";
import { Button, Tag } from "@/components/_kit";
import { cn } from "@/utils/cn";

const ACCEPTED_FORMATS = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/msword": [".doc"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
  "application/vnd.ms-powerpoint": [".ppt"]
};

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

export interface UploadZoneProps {
  onUpload: (files: File[]) => void;
  disabled?: boolean;
  status?: string;
}

export function UploadZone({ onUpload, disabled = false, status }: UploadZoneProps) {
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: unknown[]) => {
      setError(null);
      if (rejectedFiles.length > 0) {
        setError("部分文件格式不支持或超过 100MB");
        return;
      }
      if (acceptedFiles.length > 0) {
        onUpload(acceptedFiles);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_FORMATS,
    maxSize: MAX_FILE_SIZE,
    disabled,
    multiple: true
  });

  return (
    <div className="p-3">
      <div
        {...getRootProps()}
        className={cn(
          "relative flex flex-col items-center justify-center gap-2 p-6 rounded-card border-2 border-dashed",
          "transition-colors duration-micro ease-standard cursor-pointer",
          isDragActive && !isDragReject && "border-brand-500 bg-brand-50",
          isDragReject && "border-status-error bg-status-error/5",
          !isDragActive && !isDragReject && "border-border-soft hover:border-brand-400 hover:bg-surface-input",
          disabled && "opacity-50 cursor-not-allowed pointer-events-none"
        )}
      >
        <input {...getInputProps()} />
        <span
          className={cn(
            "inline-flex items-center justify-center size-10 rounded-full transition-colors duration-micro",
            isDragActive && !isDragReject ? "bg-brand-500 text-text-inverse" : "bg-surface-input text-text-muted"
          )}
          aria-hidden
        >
          {disabled ? <Loader2 className="size-5 animate-spin" /> : isDragActive ? <Upload className="size-5" /> : <FileText className="size-5" />}
        </span>
        <div className="flex flex-col items-center gap-1 text-center">
          <p className="text-body text-text-default font-medium">
            {isDragActive ? "松开鼠标上传" : "拖拽文件到此处"}
          </p>
          <p className="text-meta text-text-muted">
            或 <Button variant="ghost" size="sm" className="inline-flex">点击选择</Button>
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 justify-center">
          <Tag variant="outline" size="sm">PDF</Tag>
          <Tag variant="outline" size="sm">Word</Tag>
          <Tag variant="outline" size="sm">Excel</Tag>
          <Tag variant="outline" size="sm">PPT</Tag>
        </div>
        <p className="text-[11px] text-text-subtle">单个文件最大 100MB</p>
      </div>
      {status ? (
        <div className="mt-2 flex items-center gap-2 p-2 rounded-control bg-brand-50 border border-brand-200">
          <Loader2 className="size-3.5 animate-spin text-brand-600 shrink-0" aria-hidden />
          <p className="text-meta text-brand-700">{status}</p>
        </div>
      ) : null}
      {error ? (
        <div className="mt-2 flex items-start gap-2 p-2 rounded-control bg-status-error/5 border border-status-error/30">
          <AlertCircle className="size-3.5 text-status-error mt-0.5 shrink-0" aria-hidden />
          <p className="text-meta text-status-error">{error}</p>
        </div>
      ) : null}
    </div>
  );
}
