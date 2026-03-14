interface RequestErrorResponseData {
  message?: string
}

interface RequestErrorResponse {
  status?: number
  data?: RequestErrorResponseData
}

interface RequestErrorShape {
  response?: RequestErrorResponse
}

function getRequestErrorResponse(error: unknown) {
  if (typeof error !== "object" || error === null || !("response" in error)) {
    return undefined
  }
  return (error as RequestErrorShape).response
}

export function getRequestErrorStatus(error: unknown) {
  return getRequestErrorResponse(error)?.status
}

export function getRequestErrorMessage(error: unknown, fallbackMessage: string) {
  return getRequestErrorResponse(error)?.data?.message || fallbackMessage
}
