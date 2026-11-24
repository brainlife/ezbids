import {
    setRun,
    setIntendedFor,
    alignEntities,
    validateEntities,
    validate_B0FieldIdentifier_B0FieldSource,
    fileLogicLink,
    dwiQA,
    petQA,
    updateErrorMessages,
} from '@/libUnsafe';
import { IObject } from '@/store/store.types';

export interface ObjectsValidationContext {
    ezbids: {
        objects: IObject[];
        series: Record<number, { series_idx?: number; entities?: Record<string, string> }>;
    };
    getBIDSEntities: (type: string) => Record<string, string>;
    isExcluded: (o: IObject) => boolean;
}

export function getSomeEntities(ctx: ObjectsValidationContext, type: string): Record<string, string> {
    const entities = Object.assign({}, ctx.getBIDSEntities(type));
    delete entities.subject;
    delete entities.session;
    return entities;
}

export function validateObject(ctx: ObjectsValidationContext, o: IObject | null) {
    if (!o) return;

    o.validationErrors = [];
    o.validationWarnings = [];

    validateEntities('Objects', o);

    validate_B0FieldIdentifier_B0FieldSource(o);

    fileLogicLink(ctx.ezbids, o);

    if (o.analysisResults.warnings?.length) {
        o.validationWarnings = o.analysisResults.warnings;
    }

    const entities_requirement = ctx.getBIDSEntities(o._type);
    for (const k in getSomeEntities(ctx, o._type)) {
        if (entities_requirement[k] === 'required') {
            if (!o._entities[k]) {
                o.validationErrors.push('entity: ' + k + ' is required.');
            }
        }
    }

    for (const k in o._entities) {
        if (!['subject', 'session'].includes(k)) {
            if (o.entities[k] !== '' && !entities_requirement[k]) {
                o._entities[k] = '';
                o.entities[k] = '';
            }
        }
    }

    if (o._type.startsWith('func/')) {
        const series = ctx.ezbids.series[o.series_idx];
        if (entities_requirement['task'] && !o.entities.task && !series?.entities?.task) {
            o.validationErrors.push(
                'task entity label is required for func/bold but not set on Series Mapping page, nor overridden.'
            );
        }
    }

    if (o._type.startsWith('fmap/') || o._type === 'perf/m0scan') {
        if ((o.IntendedFor ?? []).length > 0) {
            (o.IntendedFor ?? []).forEach((i) => {
                const series_idx = ctx.ezbids.objects[i].series_idx;
                if (ctx.ezbids.objects[i]._type.startsWith('fmap/')) {
                    o.validationErrors.push(
                        'The selected series (#' +
                            series_idx +
                            ") appears to be a field map (fmap), \
                                which isn't allowed in the IntendedFor mapping. Please remove this series, or, if it \
                                isn't a field map, please correct it."
                    );
                }
            });
        }
    }

    o.items.forEach((item) => {
        if (item.sidecar) {
            try {
                item.sidecar = JSON.parse(item.sidecar_json);
            } catch (err) {
                console.error(err);
                o.validationErrors.push('Failed to parse sidecar_json. Please check the syntax');
            }
        }
    });

    if (ctx.isExcluded(o)) return;
}

export function validateAllObjects(ctx: ObjectsValidationContext) {
    alignEntities(ctx.ezbids);
    dwiQA(ctx.ezbids);
    petQA(ctx.ezbids);
    setRun(ctx.ezbids);
    ctx.ezbids.objects.forEach((o) => validateObject(ctx, o));
    setIntendedFor(ctx.ezbids);
    updateErrorMessages(ctx.ezbids);
}
