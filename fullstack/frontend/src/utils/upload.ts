const DEFAULT_ARCHIVE_UPLOAD_MAX_SIZE_MB = Number(import.meta.env.VITE_ARCHIVE_UPLOAD_MAX_SIZE_MB || 50)

export const archiveUploadMaxSizeMb = Number.isFinite(DEFAULT_ARCHIVE_UPLOAD_MAX_SIZE_MB) && DEFAULT_ARCHIVE_UPLOAD_MAX_SIZE_MB > 0
  ? DEFAULT_ARCHIVE_UPLOAD_MAX_SIZE_MB
  : 50

function getFileExtension(fileName: string) {
  return fileName.split(".").pop()?.trim().toLowerCase() || ""
}

function formatAllowedExtensions(allowedExtensions: readonly string[]) {
  return allowedExtensions.map((item) => item.toUpperCase()).join("、")
}

export function buildUploadAccept(allowedExtensions: readonly string[]) {
  return allowedExtensions.map((item) => `.${item}`).join(",")
}

export function validateUploadFiles(
  files: File[],
  options: {
    allowedExtensions: readonly string[]
    fileCategoryName: string
    maxSizeMb?: number
  },
) {
  const maxSizeMb = options.maxSizeMb || archiveUploadMaxSizeMb

  for (const file of files) {
    const fileExtension = getFileExtension(file.name)
    if (!options.allowedExtensions.includes(fileExtension)) {
      return `${options.fileCategoryName} ${file.name} 格式不支持，仅支持 ${formatAllowedExtensions(options.allowedExtensions)}。`
    }
    if (file.size > maxSizeMb * 1024 * 1024) {
      return `${options.fileCategoryName} ${file.name} 超过 ${maxSizeMb} MB，请压缩后重试。`
    }
  }

  return null
}
