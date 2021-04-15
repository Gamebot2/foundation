import * as Entity from './entity';
import * as Targets from './targets';
import * as TargetsSchema from './targetsSchema';
import * as DocTargets from './docTargets';
import memo from './util/memo';

export type Entry = {
  field: string;
  type: Entity.Type;
  is_label: boolean;
};

export type t = Entry[];

export function isEmpty(schema: t): boolean {
  return schema.length == 0;
}

export function build(): t {
  return [];
}

export function fields(schema: t): string[] {
  return schema.map(entry => entry.field);
}

export function entries(schema: t): Entry[] {
  return schema;
}

export const asDict = memo(
  function(schema: t):
    Partial<Record<string, Entry>>
  {
    const result: Partial<Record<string, Entry>> = {};
    schema.forEach(entry => result[entry.field] = entry);
    return result;
  }
);

export const entry = memo(
  function(schema: t, field: string): Entry | undefined {
    return asDict(schema)[field];
  }
);

export function hasField(schema: t, field: string): boolean {
  return schema.some(entry => entry.field == field);
}

export function type(schema: t, field: string): Entity.Type | undefined {
  return entry(schema, field)?.type;
}

export function filter(
  schema: t,
  func: (field: string) => boolean):
    t
{
  return schema.filter(entry => func(entry.field));
}

export function fieldValuePairs(
  schema: t,
  docTargets: DocTargets.t):
    Targets.FieldValuePair[]
{
  return fields(schema).map(
    field => [field, DocTargets.value(docTargets, field)]);
}