import { z } from "zod";

export const coordinatesSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
});

export type Coordinates = z.infer<typeof coordinatesSchema>;

export const eiiStatsSchema = z.object({
  geometry_type: z.string(),
  values: z.object({
    eii: z.number().optional(),
    functional_integrity: z.number().optional(),
    structural_integrity: z.number().optional(),
    compositional_integrity: z.number().optional(),
  }),
});

export type EIIStats = z.infer<typeof eiiStatsSchema>;

export const eiiRequestSchema = coordinatesSchema;

export type EIIRequest = z.infer<typeof eiiRequestSchema>;
