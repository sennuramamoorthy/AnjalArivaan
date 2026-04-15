// ── Users & Auth ──────────────────────────────────────────────────────────────
export type UserStatus = 'ACTIVE' | 'SUSPENDED' | 'PENDING_VERIFICATION';
export type UserRole =
  | 'SUPER_ADMIN'
  | 'DEPT_ADMIN'
  | 'VC'
  | 'REGISTRAR'
  | 'DEAN'
  | 'HOD'
  | 'STAFF';
export type LinkedAccountStatus = 'ACTIVE' | 'REVOKED' | 'SYNC_ERROR';

export interface AppUser {
  id: string;
  email: string;
  passwordHash: string; // ENCRYPTED at rest
  mfaSecret?: string; // ENCRYPTED at rest
  mfaEnabled: boolean;
  phone?: string; // ENCRYPTED at rest
  role: UserRole;
  status: UserStatus;
  createdAt: Date;
  updatedAt: Date;
}

export interface LinkedAccount {
  id: string;
  appUserId: string;
  googleEmail: string;
  workspaceDomain: string;
  scopes: string[];
  vaultRef: string; // Vault path, never the token itself
  status: LinkedAccountStatus;
  lastSyncAt?: Date;
  createdAt: Date;
  updatedAt: Date;
}

// ── Org Hierarchy ─────────────────────────────────────────────────────────────
export interface Employee {
  id: string;
  name: string;
  designation: string;
  department: string;
  reportingToId?: string;
  level: number;
  activeFrom: Date;
  activeTo?: Date;
  appUserId?: string;
}

export interface RoleTemplate {
  id: string;
  designation: string;
  personaPrompt: string;
  kpis: string[];
  urgencyRulesRef: string;
  briefingSchedule: string; // cron expression
}

// ── Mail ──────────────────────────────────────────────────────────────────────
export type UrgencyLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface MailMessage {
  id: string;
  accountId: string;
  gmailMsgId: string;
  threadId: string;
  from: string;
  to: string[];
  cc: string[];
  subject: string; // ENCRYPTED at rest
  bodyText?: string; // ENCRYPTED at rest
  bodyHtml?: string; // ENCRYPTED at rest
  receivedAt: Date;
  labels: string[];
  hasAttachment: boolean;
  urgencyLevel: UrgencyLevel;
  urgencyScore?: number;
  isRead: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface Attachment {
  id: string;
  mailId: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  minioKey: string;
  extractedTextRef?: string; // MinIO key for extracted text — ENCRYPTED
  ocrLang?: string;
  avTranscriptRef?: string; // MinIO key for AV transcript — ENCRYPTED
  createdAt: Date;
}

// ── Urgency Rules ─────────────────────────────────────────────────────────────
export interface UrgencyRule {
  id: string;
  role: UserRole;
  senderPatterns: string[]; // e.g. ["*.gov.in", "ugc.gov.in"]
  keywordPatterns: string[];
  deadlineRegex?: string;
  actionTemplate: string;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// ── Notifications ─────────────────────────────────────────────────────────────
export type NotificationChannel = 'WHATSAPP' | 'EMAIL' | 'PUSH' | 'IN_APP';
export type NotificationStatus = 'PENDING' | 'SENT' | 'DELIVERED' | 'FAILED';

export interface NotificationEvent {
  id: string;
  userId: string;
  channel: NotificationChannel;
  templateId: string;
  payload: Record<string, unknown>;
  status: NotificationStatus;
  deliveryReceipt?: string;
  sentAt?: Date;
  createdAt: Date;
}

// ── Meetings & Resources ──────────────────────────────────────────────────────
export type ResourceType =
  | 'CONFERENCE_ROOM'
  | 'CLASSROOM'
  | 'LAB'
  | 'EQUIPMENT'
  | 'VEHICLE'
  | 'GUESTHOUSE';
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';

export interface Resource {
  id: string;
  type: ResourceType;
  name: string;
  capacity?: number;
  location: string;
  features: string[];
  approvalRequired: boolean;
  approvers: string[];
  isActive: boolean;
}

export interface Meeting {
  id: string;
  organizer: string;
  attendees: string[];
  startAt: Date;
  endAt: Date;
  gcalEventId?: string;
  resourceIds: string[];
  agendaRef?: string;
  approvalStatus: ApprovalStatus;
  createdAt: Date;
  updatedAt: Date;
}

// ── Tasks ─────────────────────────────────────────────────────────────────────
export type TaskStatus = 'OPEN' | 'IN_PROGRESS' | 'DONE' | 'OVERDUE' | 'CANCELLED';

export interface Task {
  id: string;
  assignerId: string;
  assigneeId: string;
  subject: string;
  description?: string;
  dueAt?: Date;
  status: TaskStatus;
  sourceMailId?: string;
  replyToken?: string;
  createdAt: Date;
  updatedAt: Date;
}

// ── Travel ────────────────────────────────────────────────────────────────────
export type TravelPlanStatus =
  | 'DRAFT'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'COMPLETED';

export interface TravelPlan {
  id: string;
  travellerId: string;
  itinerary: TravelLeg[];
  advanceAmount?: number;
  approvalChain: string[];
  status: TravelPlanStatus;
  createdAt: Date;
  updatedAt: Date;
}

export interface TravelLeg {
  from: string;
  to: string;
  departAt: Date;
  arriveAt: Date;
  mode: string;
  notes?: string;
}

// ── Contacts ──────────────────────────────────────────────────────────────────
export interface Contact {
  id: string;
  accountId: string;
  name: string;
  emails: string[];
  phones: string[]; // ENCRYPTED at rest
  organization?: string;
  tags: string[];
  gmailContactId?: string;
  createdAt: Date;
  updatedAt: Date;
}

// ── Signatures & OOO ──────────────────────────────────────────────────────────
export interface Signature {
  id: string;
  accountId: string;
  name: string;
  htmlTemplate: string;
  isDefault: boolean;
  createdAt: Date;
}

export interface OOO {
  id: string;
  accountId: string;
  message: string;
  activeFrom: Date;
  activeTo: Date;
  delegateId?: string;
  gcalSynced: boolean;
  createdAt: Date;
}

// ── Audit & Compliance ────────────────────────────────────────────────────────
export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  target: string;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
  generatedContentHash?: string;
  ipAddress?: string;
  userAgent?: string;
  ts: Date;
}

export interface ConsentRecord {
  id: string;
  userId: string;
  purpose: string;
  scope: string;
  grantedAt: Date;
  revokedAt?: Date;
  proof: string;
}
