import React from "react";
import { useAuth } from "@/store/authStore";
import PageHeader from "@/components/PageHeader";

export default function Settings() {
  const { user } = useAuth();
  return (
    <div data-testid="settings-page">
      <PageHeader title="Settings" subtitle="Workspace, integrations and account preferences" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny mb-3">PROFILE</div>
          <dl className="text-sm space-y-2">
            <div className="flex justify-between"><dt className="text-zinc-500">Name</dt><dd>{user?.name}</dd></div>
            <div className="flex justify-between"><dt className="text-zinc-500">Email</dt><dd className="font-mono-stat text-xs">{user?.email}</dd></div>
            <div className="flex justify-between"><dt className="text-zinc-500">Role</dt><dd className="font-mono-stat uppercase text-xs">{user?.role?.replace("_", " ")}</dd></div>
            {user?.clientId && <div className="flex justify-between"><dt className="text-zinc-500">Client</dt><dd className="font-mono-stat text-xs truncate max-w-[180px]">{user.clientId}</dd></div>}
            {user?.resellerId && <div className="flex justify-between"><dt className="text-zinc-500">Reseller</dt><dd className="font-mono-stat text-xs truncate max-w-[180px]">{user.resellerId}</dd></div>}
          </dl>
        </div>

        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny mb-3">INTEGRATIONS</div>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">AWS S3 — Recording storage</div>
                <div className="text-xs text-zinc-500">Configured via AWS_S3_BUCKET in backend env</div>
              </div>
              <span className="px-2 py-0.5 bg-zinc-100 text-[10px] font-mono-stat rounded-sm">PLUGGABLE</span>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">MongoDB</div>
                <div className="text-xs text-zinc-500">Set MONGO_URL + DB_NAME in backend env to connect Atlas</div>
              </div>
              <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-mono-stat rounded-sm">CONNECTED</span>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">Notifications (Email / SMS / WhatsApp)</div>
                <div className="text-xs text-zinc-500">Plug in SendGrid / Twilio / WhatsApp Business API</div>
              </div>
              <span className="px-2 py-0.5 bg-zinc-100 text-[10px] font-mono-stat rounded-sm">STUB</span>
            </div>
          </div>
        </div>

        <div className="bg-white border border-zinc-200 p-5 lg:col-span-2">
          <div className="label-tiny mb-3">CONNECTING TO YOUR AWS BACKEND</div>
          <ol className="text-sm space-y-2 list-decimal pl-5 text-zinc-700">
            <li>Set <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">MONGO_URL</code> in <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">backend/.env</code> to your MongoDB Atlas connection string.</li>
            <li>Set <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">DB_NAME</code> to your existing database name. The flexible mapping layer adapts to your existing collection names — see <code>server.py</code> collection constants.</li>
            <li>For S3 recording playback, set <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">AWS_S3_BUCKET</code>, <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">AWS_REGION</code>, <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">AWS_ACCESS_KEY_ID</code> and <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">AWS_SECRET_ACCESS_KEY</code>; the <code>/api/recordings/&#123;id&#125;/signed-url</code> endpoint will generate presigned URLs via boto3.</li>
            <li>Restart the backend: <code className="font-mono-stat bg-zinc-100 px-1.5 py-0.5 rounded-sm">sudo supervisorctl restart backend</code>.</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
