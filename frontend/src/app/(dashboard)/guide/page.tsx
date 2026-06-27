'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Badge } from '@/components';

interface Step {
  title: string;
  description: string;
  details: string[];
  link?: string;
  linkLabel?: string;
}

const GUIDE_SECTIONS: { title: string; icon: string; steps: Step[] }[] = [
  {
    title: 'Getting Started',
    icon: '🚀',
    steps: [
      {
        title: '1. Set up your locations',
        description: 'Create your warehouses and shops where inventory is stored.',
        details: [
          'Go to Locations → Add Location',
          'Create at least one location (e.g., "Main Warehouse" or "Shop")',
          'You can add multiple locations for multi-branch tracking',
        ],
        link: '/locations',
        linkLabel: 'Go to Locations',
      },
      {
        title: '2. Add your categories',
        description: 'Organize your parts into categories for easy browsing.',
        details: [
          'Default categories are already seeded (Brakes, Filters, Engine Parts, etc.)',
          'Add custom categories if needed from Categories page',
          'Categories help with search, filtering, and auto-generating part numbers',
        ],
        link: '/categories',
        linkLabel: 'Go to Categories',
      },
      {
        title: '3. Add spare parts',
        description: 'Build your product catalog.',
        details: [
          'Go to Inventory → Add Part',
          'Part number is auto-generated based on category (e.g., BRK-00001)',
          'Set the cost price (what you pay) and selling price (what customers pay)',
          'Set a minimum stock level to get low-stock alerts',
          'Add initial stock right on the form: select a location and enter quantity',
          'Or leave initial stock empty and add it later from the part detail page',
        ],
        link: '/inventory',
        linkLabel: 'Go to Inventory',
      },
      {
        title: '4. Add stock to existing parts',
        description: 'Add more stock at any time.',
        details: [
          'Click on a part name in the inventory list',
          'Click "Adjust Stock" button',
          'Select the location and enter quantity (positive to add, negative to remove)',
          'Stock is immediately updated across the system',
        ],
      },
    ],
  },
  {
    title: 'Daily Operations',
    icon: '🏪',
    steps: [
      {
        title: 'Making a Sale',
        description: 'Process a customer purchase.',
        details: [
          'Go to Sales → Create Sale',
          'Select customer (or leave as "Walk-in" for cash customers)',
          'Select your location (which shop/warehouse)',
          'Choose payment type: Cash or Credit',
          'Search and add parts to the sale',
          'Click "Save & Confirm" to deduct stock and generate invoice',
          'Or "Save as Draft" to complete later',
        ],
        link: '/sales/create',
        linkLabel: 'Create a Sale',
      },
      {
        title: 'Processing a Return',
        description: 'Handle when a customer brings parts back.',
        details: [
          'Go to Sales → click on the confirmed sale',
          'Click "Process Return"',
          'Select which items to return and the quantity',
          'Stock is automatically restored',
          'The sale shows a Return Summary with net amount',
        ],
        link: '/sales',
        linkLabel: 'Go to Sales',
      },
      {
        title: 'Recording a Payment',
        description: 'When a credit customer pays their balance.',
        details: [
          'Go to Customers → click customer name',
          'Go to the "Credit Ledger" tab',
          'Click "Record Payment"',
          'Enter the amount received',
          'The customer balance is automatically reduced',
        ],
        link: '/customers',
        linkLabel: 'Go to Customers',
      },
    ],
  },
  {
    title: 'Purchasing & Restocking',
    icon: '📦',
    steps: [
      {
        title: 'Creating a Purchase Order',
        description: 'Order new stock from a supplier.',
        details: [
          'Go to Purchases → Create PO',
          'Select the supplier',
          'Add line items: which parts, how many, and at what cost',
          'Submit as Draft — needs approval from a Manager',
        ],
        link: '/purchases',
        linkLabel: 'Go to Purchases',
      },
      {
        title: 'Approving a PO',
        description: 'Manager reviews and approves the order.',
        details: [
          'Click on the PO → click "Approve"',
          'The PO status changes to Approved',
          'You can now send it to the supplier',
        ],
      },
      {
        title: 'Receiving Goods (GRN)',
        description: 'When the supplier delivers the parts.',
        details: [
          'Click on an Approved PO → "Mark Received"',
          'Select the receiving location',
          'Enter quantities actually received',
          'Stock is automatically added to that location',
          'Cost layers are created for FIFO tracking',
        ],
      },
    ],
  },
  {
    title: 'Transfers',
    icon: '🔄',
    steps: [
      {
        title: 'Moving Stock Between Locations',
        description: 'Transfer parts from one warehouse/shop to another.',
        details: [
          'Go to Transfers → Create Transfer',
          'Select the part, source location, destination, and quantity',
          'A Manager approves the transfer',
          'The stock moves through In-Transit state',
          'Destination confirms receipt',
        ],
        link: '/transfers',
        linkLabel: 'Go to Transfers',
      },
    ],
  },
  {
    title: 'Reports & Insights',
    icon: '📊',
    steps: [
      {
        title: 'Generating Reports',
        description: 'Get business insights.',
        details: [
          'Go to Reports → select report type',
          'Sales Report: revenue by period',
          'Inventory Report: stock values and low-stock items',
          'Customer Report: balances and aging',
          'Supplier Report: outstanding amounts',
        ],
        link: '/reports',
        linkLabel: 'Go to Reports',
      },
      {
        title: 'Dashboard',
        description: 'Quick overview of your business.',
        details: [
          'Dashboard shows today\'s sales, monthly total, and outstanding receivables',
          'Low stock count tells you how many parts need reordering',
          'Top selling products shows your best performers',
          'Data refreshes every 5 minutes automatically',
        ],
        link: '/dashboard',
        linkLabel: 'Go to Dashboard',
      },
    ],
  },
  {
    title: 'Settings & Admin',
    icon: '⚙️',
    steps: [
      {
        title: 'Managing Users',
        description: 'Create accounts for your staff.',
        details: [
          'Go to Settings → Create User',
          'Roles: Admin (full access), Manager (approvals + reports), Salesperson (sales only), Storekeeper (inventory only)',
          'Set a strong password (min 8 chars, uppercase, lowercase, digit)',
        ],
        link: '/settings',
        linkLabel: 'Go to Settings',
      },
      {
        title: 'Currency Settings',
        description: 'Change the display currency.',
        details: [
          'Go to Settings → System Settings section',
          'Select your preferred currency (NGN, USD, GBP, etc.)',
          'All prices across the app will update',
        ],
        link: '/settings',
        linkLabel: 'Go to Settings',
      },
    ],
  },
];

export default function GuidePage() {
  const router = useRouter();
  const [expandedSection, setExpandedSection] = useState<number>(0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">How to Use AutoStockManager</h1>
        <p className="mt-1 text-sm text-gray-500">
          A step-by-step guide to managing your auto spare parts business
        </p>
      </div>

      {/* Quick tip */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 p-4">
        <p className="text-sm text-blue-800">
          <strong>Quick Start:</strong> Set up locations → Add parts → Add stock → Start selling. 
          Follow the sections below in order for the best experience.
        </p>
      </div>

      {/* Sections */}
      <div className="space-y-4">
        {GUIDE_SECTIONS.map((section, sectionIndex) => (
          <div
            key={section.title}
            className="rounded-lg border border-gray-200 bg-white overflow-hidden"
          >
            {/* Section header */}
            <button
              type="button"
              onClick={() => setExpandedSection(expandedSection === sectionIndex ? -1 : sectionIndex)}
              className="flex w-full items-center justify-between px-4 py-4 sm:px-6 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl" aria-hidden="true">{section.icon}</span>
                <h2 className="text-lg font-semibold text-gray-900">{section.title}</h2>
                <Badge variant="default">{section.steps.length} steps</Badge>
              </div>
              <svg
                className={`h-5 w-5 text-gray-400 transition-transform ${expandedSection === sectionIndex ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Section content */}
            {expandedSection === sectionIndex && (
              <div className="border-t border-gray-200 px-4 py-4 sm:px-6 space-y-6">
                {section.steps.map((step, stepIndex) => (
                  <div key={stepIndex} className="space-y-2">
                    <h3 className="font-semibold text-gray-900">{step.title}</h3>
                    <p className="text-sm text-gray-600">{step.description}</p>
                    <ul className="list-disc list-inside space-y-1 text-sm text-gray-700 pl-2">
                      {step.details.map((detail, i) => (
                        <li key={i}>{detail}</li>
                      ))}
                    </ul>
                    {step.link && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => router.push(step.link!)}
                      >
                        {step.linkLabel} →
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
