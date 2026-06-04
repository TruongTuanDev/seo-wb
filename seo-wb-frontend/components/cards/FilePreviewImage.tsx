"use client";

import React, { useEffect, useMemo } from "react";

export function FilePreviewImage({
  file,
  alt,
  className,
  onClick,
}: {
  file: File;
  alt: string;
  className?: string;
  onClick?: (url: string, file: File) => void;
}) {
  const url = useMemo(() => URL.createObjectURL(file), [file]);

  useEffect(() => {
    return () => URL.revokeObjectURL(url);
  }, [url]);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt}
      draggable={false}
      onClick={() => onClick?.(url, file)}
      className={className}
    />
  );
}
