/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_API_TEXTBOOKS?: string;
  readonly VITE_API_GRAPH?: string;
  readonly VITE_API_INTEGRATION?: string;
  readonly VITE_API_RAG?: string;
  readonly VITE_API_DIALOGUE?: string;
  readonly VITE_API_REPORT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
