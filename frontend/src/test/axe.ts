/**
 * Automated accessibility scanning helper for component tests.
 *
 * Uses axe-core against rendered markup. jsdom has no layout engine, so
 * layout-dependent rules (contrast, visibility geometry) are excluded here and
 * covered by the browser-based Playwright scan instead.
 *
 * Requirements: 19.4, 19.6
 */

import axe, { type ImpactValue, type Result } from 'axe-core';

const BLOCKING_IMPACTS: ImpactValue[] = ['critical', 'serious'];

const LAYOUT_DEPENDENT_RULES = ['color-contrast', 'target-size'];

export interface AxeFinding {
  id: string;
  impact: ImpactValue | null | undefined;
  help: string;
  nodes: string[];
}

export async function findAccessibilityViolations(container: Element): Promise<AxeFinding[]> {
  const results = await axe.run(container, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
    rules: Object.fromEntries(
      LAYOUT_DEPENDENT_RULES.map((rule) => [rule, { enabled: false }]),
    ),
  });

  return results.violations
    .filter((violation: Result) => BLOCKING_IMPACTS.includes(violation.impact as ImpactValue))
    .map((violation: Result) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
      nodes: violation.nodes.map((node) => node.html),
    }));
}
