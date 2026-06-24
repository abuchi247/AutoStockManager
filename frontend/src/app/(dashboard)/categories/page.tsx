'use client';

/**
 * Categories Management Page
 *
 * Displays a tree/table of categories with parent/child indentation.
 * Supports create, edit, and delete operations.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { get, post, put, del } from '@/lib/api';
import {
  Button,
  Input,
  Select,
  Badge,
  Modal,
  Alert,
} from '@/components';
import type { SelectOption } from '@/components';

interface CategoryItem {
  id: string;
  name: string;
  parent_id: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  children: CategoryItem[];
  spare_parts_count: number;
}

interface CategoryListResponse {
  data: CategoryItem[];
  meta: { page: number; total: number; page_size: number };
}

export default function CategoriesPage() {
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newCategory, setNewCategory] = useState({
    name: '',
    parent_id: '',
    description: '',
    is_active: true,
  });

  // Edit modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState<{
    id: string;
    name: string;
    parent_id: string;
    description: string;
    is_active: boolean;
  } | null>(null);

  // Delete confirmation
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CategoryItem | null>(null);

  const fetchCategories = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<CategoryListResponse>(
        '/categories?page_size=500'
      );
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

  // Get flat list of top-level categories for parent dropdown
  const parentOptions: SelectOption[] = [
    { value: '', label: 'None (Top-level)' },
    ...categories
      .filter((c) => !c.parent_id)
      .map((c) => ({ value: c.id, label: c.name })),
  ];

  const handleCreateCategory = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      const payload: Record<string, unknown> = {
        name: newCategory.name,
        is_active: newCategory.is_active,
      };
      if (newCategory.parent_id) payload.parent_id = newCategory.parent_id;
      if (newCategory.description) payload.description = newCategory.description;

      await post('/categories', payload);
      setShowCreateModal(false);
      setNewCategory({ name: '', parent_id: '', description: '', is_active: true });
      fetchCategories();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create category';
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleEditCategory = async () => {
    if (!editCategory) return;
    setIsEditing(true);
    setEditError(null);
    try {
      const payload: Record<string, unknown> = {
        name: editCategory.name,
        is_active: editCategory.is_active,
      };
      if (editCategory.parent_id) payload.parent_id = editCategory.parent_id;
      if (editCategory.description) payload.description = editCategory.description;

      await put(`/categories/${editCategory.id}`, payload);
      setShowEditModal(false);
      setEditCategory(null);
      fetchCategories();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update category';
      setEditError(message);
    } finally {
      setIsEditing(false);
    }
  };

  const handleDeleteCategory = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await del(`/categories/${deleteTarget.id}`);
      setShowDeleteModal(false);
      setDeleteTarget(null);
      fetchCategories();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete category';
      setError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  const openEditModal = (cat: CategoryItem) => {
    setEditCategory({
      id: cat.id,
      name: cat.name,
      parent_id: cat.parent_id || '',
      description: cat.description || '',
      is_active: cat.is_active,
    });
    setEditError(null);
    setShowEditModal(true);
  };

  const openDeleteModal = (cat: CategoryItem) => {
    setDeleteTarget(cat);
    setShowDeleteModal(true);
  };

  // Render category row with indentation
  const renderCategoryRow = (cat: CategoryItem, level: number = 0) => {
    const rows: React.ReactNode[] = [];

    rows.push(
      <tr key={cat.id} className={level > 0 ? 'bg-gray-50/50' : 'bg-white'}>
        <td className="px-6 py-4 whitespace-nowrap">
          <div style={{ paddingLeft: `${level * 24}px` }} className="flex items-center gap-2">
            {level > 0 && (
              <span className="text-gray-400">└</span>
            )}
            <span className={`font-medium ${level === 0 ? 'text-gray-900' : 'text-gray-700'}`}>
              {cat.name}
            </span>
          </div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {cat.description || '—'}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-center">
          <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
            {cat.spare_parts_count}
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-center">
          {cat.is_active ? (
            <Badge variant="success">Active</Badge>
          ) : (
            <Badge variant="danger">Inactive</Badge>
          )}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
          <button
            type="button"
            onClick={() => openEditModal(cat)}
            className="text-blue-600 hover:text-blue-800 mr-3"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => openDeleteModal(cat)}
            className="text-red-600 hover:text-red-800"
          >
            Delete
          </button>
        </td>
      </tr>
    );

    // Render children
    if (cat.children && cat.children.length > 0) {
      for (const child of cat.children) {
        rows.push(...renderCategoryRow(child, level + 1) as unknown as React.ReactNode[]);
      }
    }

    return rows;
  };

  // Build tree: only show top-level categories with their children nested
  const topLevelCategories = categories.filter((c) => !c.parent_id);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Categories</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage product categories and subcategories
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>Add Category</Button>
      </div>

      {/* Error display */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Categories table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Description
              </th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">
                Parts
              </th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  <div className="flex items-center justify-center gap-2">
                    <svg className="h-5 w-5 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Loading categories...
                  </div>
                </td>
              </tr>
            ) : topLevelCategories.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  No categories found. Add your first category to get started.
                </td>
              </tr>
            ) : (
              topLevelCategories.map((cat) => renderCategoryRow(cat, 0))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Category Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Add New Category"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowCreateModal(false);
                setCreateError(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleCreateCategory} isLoading={isCreating}>
              Create Category
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {createError && (
            <Alert variant="error" onClose={() => setCreateError(null)}>
              {createError}
            </Alert>
          )}
          <Input
            label="Name"
            value={newCategory.name}
            onChange={(e) =>
              setNewCategory({ ...newCategory, name: e.target.value })
            }
            required
          />
          <Select
            label="Parent Category"
            options={parentOptions}
            value={newCategory.parent_id}
            onChange={(e) =>
              setNewCategory({ ...newCategory, parent_id: e.target.value })
            }
          />
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
              rows={3}
              value={newCategory.description}
              onChange={(e) =>
                setNewCategory({ ...newCategory, description: e.target.value })
              }
              placeholder="Category description..."
            />
          </div>
        </div>
      </Modal>

      {/* Edit Category Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditError(null);
        }}
        title="Edit Category"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowEditModal(false);
                setEditError(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleEditCategory} isLoading={isEditing}>
              Save Changes
            </Button>
          </>
        }
      >
        {editCategory && (
          <div className="space-y-4">
            {editError && (
              <Alert variant="error" onClose={() => setEditError(null)}>
                {editError}
              </Alert>
            )}
            <Input
              label="Name"
              value={editCategory.name}
              onChange={(e) =>
                setEditCategory({ ...editCategory, name: e.target.value })
              }
              required
            />
            <Select
              label="Parent Category"
              options={parentOptions.filter((o) => o.value !== editCategory.id)}
              value={editCategory.parent_id}
              onChange={(e) =>
                setEditCategory({ ...editCategory, parent_id: e.target.value })
              }
            />
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
                rows={3}
                value={editCategory.description}
                onChange={(e) =>
                  setEditCategory({ ...editCategory, description: e.target.value })
                }
                placeholder="Category description..."
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="edit-is-active"
                checked={editCategory.is_active}
                onChange={(e) =>
                  setEditCategory({ ...editCategory, is_active: e.target.checked })
                }
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="edit-is-active" className="text-sm text-gray-700">
                Active
              </label>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Delete Category"
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setShowDeleteModal(false)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDeleteCategory}
              isLoading={isDeleting}
            >
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          Are you sure you want to delete{' '}
          <span className="font-medium text-gray-900">
            {deleteTarget?.name}
          </span>
          ? This action cannot be undone.
          {deleteTarget?.children && deleteTarget.children.length > 0 && (
            <span className="mt-2 block text-amber-600">
              ⚠️ This category has {deleteTarget.children.length} subcategories that may be affected.
            </span>
          )}
        </p>
      </Modal>
    </div>
  );
}
