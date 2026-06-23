'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { get, post, put, del } from '@/lib/api';
import {
  Button,
  Input,
  Modal,
  Alert,
  LoadingSpinner,
} from '@/components';
import type { Category } from '@/lib/types';

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create/Edit modal
  const [showModal, setShowModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formParentId, setFormParentId] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Delete confirmation
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingCategory, setDeletingCategory] = useState<Category | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchCategories = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<{ data: Category[] }>('/spare-parts/categories');
      setCategories(response.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load categories';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const openCreateModal = () => {
    setEditingCategory(null);
    setFormName('');
    setFormDescription('');
    setFormParentId('');
    setSaveError(null);
    setShowModal(true);
  };

  const openEditModal = (category: Category) => {
    setEditingCategory(category);
    setFormName(category.name);
    setFormDescription(category.description || '');
    setFormParentId(category.parent_id || '');
    setSaveError(null);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) {
      setSaveError('Category name is required');
      return;
    }

    setIsSaving(true);
    setSaveError(null);
    try {
      const payload = {
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        parent_id: formParentId || undefined,
      };

      if (editingCategory) {
        await put(`/spare-parts/categories/${editingCategory.id}`, payload);
      } else {
        await post('/spare-parts/categories', payload);
      }

      setShowModal(false);
      fetchCategories();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save category';
      setSaveError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingCategory) return;
    setIsDeleting(true);
    try {
      await del(`/spare-parts/categories/${deletingCategory.id}`);
      setShowDeleteModal(false);
      setDeletingCategory(null);
      fetchCategories();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete category';
      setError(message);
      setShowDeleteModal(false);
    } finally {
      setIsDeleting(false);
    }
  };

  const getParentName = (parentId?: string): string => {
    if (!parentId) return '—';
    const parent = categories.find((c) => c.id === parentId);
    return parent?.name || '—';
  };

  // Build tree structure for display
  const topLevelCategories = categories.filter((c) => !c.parent_id);
  const getChildren = (parentId: string) =>
    categories.filter((c) => c.parent_id === parentId);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Categories</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage spare part categories and subcategories
          </p>
        </div>
        <Button onClick={openCreateModal}>Add Category</Button>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Categories list */}
      <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
        {categories.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-gray-500">
            No categories found. Create your first category to get started.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {topLevelCategories.map((category) => (
              <div key={category.id}>
                <CategoryRow
                  category={category}
                  level={0}
                  onEdit={openEditModal}
                  onDelete={(c) => {
                    setDeletingCategory(c);
                    setShowDeleteModal(true);
                  }}
                />
                {getChildren(category.id).map((child) => (
                  <CategoryRow
                    key={child.id}
                    category={child}
                    level={1}
                    onEdit={openEditModal}
                    onDelete={(c) => {
                      setDeletingCategory(c);
                      setShowDeleteModal(true);
                    }}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingCategory ? 'Edit Category' : 'Create Category'}
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} isLoading={isSaving}>
              {editingCategory ? 'Save Changes' : 'Create'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {saveError && (
            <Alert variant="error" onClose={() => setSaveError(null)}>
              {saveError}
            </Alert>
          )}
          <Input
            label="Name"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            required
            placeholder="Category name"
          />
          <Input
            label="Description"
            value={formDescription}
            onChange={(e) => setFormDescription(e.target.value)}
            placeholder="Optional description"
          />
          <div className="w-full">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Parent Category
            </label>
            <select
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
              value={formParentId}
              onChange={(e) => setFormParentId(e.target.value)}
            >
              <option value="">None (top-level)</option>
              {categories
                .filter((c) => c.id !== editingCategory?.id && !c.parent_id)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </select>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Delete Category"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          Are you sure you want to delete the category{' '}
          <strong>{deletingCategory?.name}</strong>? Parts in this category will
          become uncategorized.
        </p>
      </Modal>
    </div>
  );
}

function CategoryRow({
  category,
  level,
  onEdit,
  onDelete,
}: {
  category: Category;
  level: number;
  onEdit: (c: Category) => void;
  onDelete: (c: Category) => void;
}) {
  return (
    <div
      className="flex items-center justify-between px-6 py-3 hover:bg-gray-50"
      style={{ paddingLeft: `${1.5 + level * 1.5}rem` }}
    >
      <div className="flex items-center gap-3">
        {level > 0 && (
          <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        )}
        <div>
          <p className="text-sm font-medium text-gray-900">{category.name}</p>
          {category.description && (
            <p className="text-xs text-gray-500">{category.description}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onEdit(category)}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          aria-label={`Edit ${category.name}`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => onDelete(category)}
          className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600"
          aria-label={`Delete ${category.name}`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>
  );
}
