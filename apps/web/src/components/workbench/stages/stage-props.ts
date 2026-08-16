import type { ChangeEvent } from "react";

import type { WorkspaceSnapshot } from "../../../lib/workspace-model";

export interface StageProps {
  snapshot: WorkspaceSnapshot;
  sourceFile: File | null;
  busy: boolean;
  rejectReason: string;
  rejectNote: string;
  reviewSummary: string;
  reviewChanges: string;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onUpload: () => void;
  onParse: () => void;
  onAccept: () => void;
  onReject: () => void;
  onRejectReasonChange: (value: string) => void;
  onRejectNoteChange: (value: string) => void;
  onGenerateConcepts: () => void;
  onSelectConcept: (candidateId: string) => void;
  onGenerateScript: () => void;
  onGenerateStoryboard: () => void;
  onGenerateShotPlan: () => void;
  onReviewSummaryChange: (value: string) => void;
  onReviewChangesChange: (value: string) => void;
  onApprove: () => void;
  onRequestChanges: () => void;
  onCompleteRevision: () => void;
  onCancelRevision: () => void;
  onCreateDelivery: () => void;
  onExportDelivery: () => void;
  onDownload: (exportId: string, filename: string) => void;
  download: { downloadUrl: string; filename: string } | null;
}
