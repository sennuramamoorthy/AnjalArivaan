import { apiClient } from './client';

export type TaskStatus =
  | 'OPEN'
  | 'IN_PROGRESS'
  | 'DONE'
  | 'OVERDUE'
  | 'CANCELLED';

export interface Task {
  id: string;
  subject: string;
  description: string | null;
  status: TaskStatus;
  dueAt: string | null;
  assigneeId: string;
  assignerId: string;
  sourceMailId: string | null;
  replyToken: string | null;
}

export interface CreateTaskInput {
  subject: string;
  description?: string;
  dueAt?: string;
  assigneeId?: string;
  sourceMailId?: string;
}

export interface UpdateTaskInput {
  subject?: string;
  description?: string;
  status?: TaskStatus;
  dueAt?: string;
}

export function listTasks(params: { status?: TaskStatus; limit?: number } = {}): Promise<Task[]> {
  return apiClient.get<Task[]>('/api/v1/tasks', { params });
}

export function getTask(taskId: string): Promise<Task> {
  return apiClient.get<Task>(`/api/v1/tasks/${taskId}`);
}

export function createTask(input: CreateTaskInput): Promise<Task> {
  return apiClient.post<Task>('/api/v1/tasks', {
    subject: input.subject,
    description: input.description,
    due_at: input.dueAt,
    assignee_id: input.assigneeId,
    source_mail_id: input.sourceMailId,
  });
}

export function updateTask(taskId: string, input: UpdateTaskInput): Promise<Task> {
  return apiClient.patch<Task>(`/api/v1/tasks/${taskId}`, {
    subject: input.subject,
    description: input.description,
    status: input.status,
    due_at: input.dueAt,
  });
}

export function deleteTask(taskId: string): Promise<{ deleted: boolean }> {
  return apiClient.delete<{ deleted: boolean }>(`/api/v1/tasks/${taskId}`);
}
