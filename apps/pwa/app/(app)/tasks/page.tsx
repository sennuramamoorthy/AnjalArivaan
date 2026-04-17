'use client';

/**
 * /tasks — Phase 1a task management view.
 *
 * Per D10, tasks are primarily email-derived (assigned via email, tracked
 * via reply parsing). This page surfaces the list + provides manual CRUD
 * for the PWA, hitting the `/api/v1/tasks` endpoints.
 */

import * as React from 'react';
import { CheckCircle2, Circle, Loader2, Plus, Trash2 } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useTasks,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
} from '@/lib/hooks/use-tasks';
import type { Task, TaskStatus } from '@/lib/api/tasks';

const STATUS_FILTERS: Array<{ label: string; value?: TaskStatus }> = [
  { label: 'All' },
  { label: 'Open', value: 'OPEN' },
  { label: 'In Progress', value: 'IN_PROGRESS' },
  { label: 'Done', value: 'DONE' },
];

function StatusBadge({ status }: { status: TaskStatus }) {
  const styles: Record<TaskStatus, string> = {
    OPEN: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
    IN_PROGRESS:
      'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
    DONE: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
    OVERDUE: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
    CANCELLED:
      'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      {status.replace('_', ' ').toLowerCase()}
    </span>
  );
}

function TaskRow({ task }: { task: Task }) {
  const update = useUpdateTask();
  const remove = useDeleteTask();

  const isDone = task.status === 'DONE';
  const toggle = () =>
    update.mutate({
      id: task.id,
      input: { status: isDone ? 'OPEN' : 'DONE' },
    });

  return (
    <li className="flex items-start gap-3 border-b border-gray-200 px-4 py-3 dark:border-gray-800">
      <button
        onClick={toggle}
        disabled={update.isPending}
        className="mt-0.5 shrink-0 text-gray-400 hover:text-emerald-600 dark:text-gray-500 dark:hover:text-emerald-400"
        aria-label={isDone ? 'Mark open' : 'Mark done'}
      >
        {isDone ? (
          <CheckCircle2 size={20} className="text-emerald-500" />
        ) : (
          <Circle size={20} />
        )}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={`truncate text-sm font-medium ${
              isDone
                ? 'text-gray-400 line-through dark:text-gray-500'
                : 'text-gray-900 dark:text-gray-100'
            }`}
          >
            {task.subject}
          </span>
          <StatusBadge status={task.status} />
        </div>
        {task.description && (
          <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
            {task.description}
          </p>
        )}
        {task.dueAt && (
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Due {new Date(task.dueAt).toLocaleDateString()}
          </p>
        )}
      </div>
      <button
        onClick={() => remove.mutate(task.id)}
        disabled={remove.isPending}
        className="shrink-0 rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
        aria-label="Delete task"
      >
        <Trash2 size={16} />
      </button>
    </li>
  );
}

function NewTaskForm() {
  const [subject, setSubject] = React.useState('');
  const create = useCreateTask();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = subject.trim();
    if (!trimmed) return;
    create.mutate(
      { subject: trimmed },
      {
        onSuccess: () => setSubject(''),
      },
    );
  };

  return (
    <form onSubmit={submit} className="flex gap-2 p-4">
      <Input
        placeholder="Add a task — e.g. 'Approve NAAC report'"
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        disabled={create.isPending}
        className="flex-1"
      />
      <Button type="submit" disabled={!subject.trim() || create.isPending}>
        {create.isPending ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Plus size={16} />
        )}
        <span className="ml-1">Add</span>
      </Button>
    </form>
  );
}

export default function TasksPage() {
  const [filter, setFilter] = React.useState<TaskStatus | undefined>(undefined);
  const { data: tasks, isLoading, error } = useTasks({ status: filter });

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-gray-200 px-6 py-4 dark:border-gray-800">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
          Tasks
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Email-derived action items, assignments, and follow-ups.
        </p>
      </header>

      <div className="border-b border-gray-200 px-6 py-3 dark:border-gray-800">
        <div className="flex gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => setFilter(f.value)}
              className={`rounded-full px-3 py-1 text-sm ${
                filter === f.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <Card className="mx-auto mt-6 max-w-3xl">
          <NewTaskForm />
          {isLoading ? (
            <div className="space-y-2 p-4">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-5 w-2/3" />
            </div>
          ) : error ? (
            <div className="p-6 text-sm text-red-600">
              Could not load tasks. Try refreshing.
            </div>
          ) : !tasks || tasks.length === 0 ? (
            <div className="p-10 text-center text-sm text-gray-500 dark:text-gray-400">
              <Badge variant="success" className="mb-2">
                All clear
              </Badge>
              <p>No tasks match this filter.</p>
            </div>
          ) : (
            <ul>
              {tasks.map((t) => (
                <TaskRow key={t.id} task={t} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
