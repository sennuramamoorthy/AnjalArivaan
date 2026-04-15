export interface BaseEvent {
  eventId: string;
  eventType: string;
  accountId: string;
  userId: string;
  traceId: string;
  occurredAt: string; // ISO 8601
}

export interface NewMailEvent extends BaseEvent {
  eventType: 'mail.new';
  mailId: string;
  gmailMsgId: string;
  threadId: string;
  from: string;
  subject: string;
  receivedAt: string;
  hasAttachment: boolean;
}

export interface UrgencyDetectedEvent extends BaseEvent {
  eventType: 'mail.urgency_detected';
  mailId: string;
  urgencyLevel: 'HIGH' | 'CRITICAL';
  urgencyScore: number;
  ruleId: string;
  detectedDeadline?: string;
}

export interface AttachmentReadyEvent extends BaseEvent {
  eventType: 'attachment.ready';
  attachmentId: string;
  mailId: string;
  minioKey: string;
  mimeType: string;
}

export interface BriefingRequestEvent extends BaseEvent {
  eventType: 'briefing.requested';
  scheduledFor: string;
  channels: string[];
}
