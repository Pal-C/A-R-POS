import axe from 'axe-core'

/**
 * Fails the test when axe finds serious or critical accessibility violations
 * (research R10). Color contrast can't be computed in jsdom; it is covered by the
 * token contrast table and the manual quickstart check.
 */
export async function expectNoAxeViolations(container: Element): Promise<void> {
  const results = await axe.run(container, {
    rules: { 'color-contrast': { enabled: false }, region: { enabled: false } },
  })
  const blocking = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  if (blocking.length > 0) {
    const summary = blocking
      .map((v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.map((n) => n.target.join(' ')).join('\n  ')}`)
      .join('\n')
    throw new Error(`Accessibility violations:\n${summary}`)
  }
}
