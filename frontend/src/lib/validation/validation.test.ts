import {
  customerCreateSchema,
  purchaseOrderCreateSchema,
  transferCreateSchema,
} from './schemas';
import { fastApiPathToField, mapFastAPIValidationErrors, validateWithSchema } from './errors';

describe('domain form validation', () => {
  it('rejects a customer without the backend-required name', () => {
    const result = validateWithSchema(customerCreateSchema, { credit_limit: 0 });
    expect(result.errors.name).toBe('Name is required');
  });

  it('accepts a valid purchase order and rejects empty line items', () => {
    const valid = purchaseOrderCreateSchema.safeParse({
      supplier_id: '00000000-0000-0000-0000-000000000001',
      items: [{ spare_part_id: '00000000-0000-0000-0000-000000000002', quantity_ordered: 2, unit_cost: 10 }],
    });
    expect(valid.success).toBe(true);
    expect(purchaseOrderCreateSchema.safeParse({ supplier_id: '00000000-0000-0000-0000-000000000001', items: [] }).success).toBe(false);
  });

  it('rejects transfers between the same location', () => {
    const result = transferCreateSchema.safeParse({
      spare_part_id: '00000000-0000-0000-0000-000000000001',
      source_location_id: '00000000-0000-0000-0000-000000000002',
      destination_location_id: '00000000-0000-0000-0000-000000000002',
      quantity: 1,
    });
    expect(result.success).toBe(false);
  });

  it('maps nested FastAPI locations to React Hook Form paths', () => {
    expect(fastApiPathToField(['body', 'items', 0, 'quantity'])).toBe('items.0.quantity');
    expect(mapFastAPIValidationErrors({ response: { data: { detail: [{ loc: ['body', 'items', 0, 'quantity'], msg: 'Must be greater than zero' }] } } })).toEqual({ 'items.0.quantity': 'Must be greater than zero' });
  });
});
