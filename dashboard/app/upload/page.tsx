import { UploadForm } from "@/components/upload-form";

export const metadata = { title: "Upload & analyze" };

export default function UploadPage() {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">
          Upload &amp; analyze
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Drop an audio recording to run the full support pipeline: transcribe,
          analyze, create an incident form, and send a notification email.
        </p>
      </div>

      <UploadForm />
    </div>
  );
}
