/**
 * Shared TypeScript types that mirror the Pydantic schemas on the backend.
 * Keeping these in one file makes it easy to regenerate from OpenAPI later.
 */

export type ISODateTime = string;

// ---------- auth ---------------------------------------------------------
export interface UserOut {
  id: number;
  email: string;
  full_name: string;
  designation: string | null;
  department: string | null;
  is_super_admin: boolean;
  is_dept_admin: boolean;
  reporting_to_id: number | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface MfaSetup {
  secret: string;
  otpauth_uri: string;
}

// ---------- accounts -----------------------------------------------------
export interface LinkedAccountOut {
  id: number;
  app_user_id: number;
  google_email: string;
  workspace_domain: string;
  status: "PENDING" | "ACTIVE" | "REVOKED" | "ERROR";
  scopes: string[];
  gmail_history_id: string | null;
  created_at: ISODateTime;
}

// ---------- mail ---------------------------------------------------------
export interface MailMessageOut {
  id: number;
  thread_id: string;
  gmail_msg_id: string;
  from_address: string;
  to_addresses: string[];
  subject: string;
  preview: string;
  received_at: ISODateTime;
  is_urgent: boolean;
  urgency_score: number;
  has_attachments: boolean;
}

export interface MailThreadOut {
  thread_id: string;
  subject: string;
  participants: string[];
  message_count: number;
  last_activity: ISODateTime;
  messages: MailMessageOut[];
}

// ---------- meetings / resources -----------------------------------------
export interface ResourceOut {
  id: number;
  name: string;
  type: "CONFERENCE_ROOM" | "CLASSROOM" | "LAB" | "EQUIPMENT" | "VEHICLE" | "GUESTHOUSE";
  location: string | null;
  capacity: number | null;
  active: boolean;
}

export interface MeetingOut {
  id: number;
  title: string;
  description: string | null;
  start_at: ISODateTime;
  end_at: ISODateTime;
  organizer_email: string;
  attendees: string[];
  location: string | null;
  google_event_id: string | null;
  resource_ids: number[];
  status: string;
}

// ---------- tasks --------------------------------------------------------
export type TaskState =
  | "ASSIGNED"
  | "ACKNOWLEDGED"
  | "IN_PROGRESS"
  | "BLOCKED"
  | "DONE"
  | "CANCELLED";

export interface TaskOut {
  id: number;
  title: string;
  description: string | null;
  assignee_email: string;
  assigner_email: string;
  state: TaskState;
  due_at: ISODateTime | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

// ---------- travel -------------------------------------------------------
export interface TravelPlanOut {
  id: number;
  traveler_email: string;
  destination: string;
  purpose: string;
  depart_at: ISODateTime;
  return_at: ISODateTime;
  mode: string;
  status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "COMPLETED";
  approver_email: string | null;
  notes: string | null;
}

// ---------- contacts -----------------------------------------------------
export interface ContactOut {
  id: number;
  display_name: string;
  email: string;
  phone_e164: string | null;
  title: string | null;
  organization: string | null;
  relationship: string | null;
  note: string | null;
}

export interface SignatureOut {
  id: number;
  label: string;
  html_body: string;
  is_default: boolean;
}

export interface OutOfOfficeOut {
  id: number;
  enabled: boolean;
  subject: string;
  body: string;
  start_at: ISODateTime | null;
  end_at: ISODateTime | null;
}

// ---------- briefing / ai ------------------------------------------------
export interface BriefingItem {
  kind: "URGENT_MAIL" | "MEETING" | "TASK" | "TRAVEL" | "REMINDER";
  title: string;
  summary: string;
  link?: string;
  when?: ISODateTime;
}

export interface BriefingResponse {
  generated_at: ISODateTime;
  greeting: string;
  items: BriefingItem[];
}

export interface DraftReplyResponse {
  draft_subject: string;
  draft_body_html: string;
  model: string;
  prompt_version: string;
}

// ---------- search -------------------------------------------------------
export interface SearchHit {
  id: string;
  source_type: "MAIL" | "CALENDAR" | "CONTACT" | "TASK" | "TRAVEL" | "DOCUMENT";
  score: number;
  title: string;
  preview: string;
  link?: string;
}

// ---------- errors -------------------------------------------------------
export interface ApiError {
  detail: string;
  code?: string;
}
