import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { UploadForm } from "@/components/upload-form";

export const metadata = { title: "Upload & analyze" };

export default function UploadPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">Upload &amp; analyze audio</h1>
        <p className="text-sm text-muted-foreground">
          Demo flow: drop a recording in, the support pipeline transcribes it, an AI fills out an
          incident form, and the result is emailed and stored in the database.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New analysis</CardTitle>
          <CardDescription>
            Forwards your file to the voice-app service. Use Mailpit (Inbox) to inspect the
            generated notification email.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <UploadForm />
        </CardContent>
      </Card>
    </div>
  );
}
