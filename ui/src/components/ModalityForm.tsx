import React, { useState, useCallback, useRef, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';

import anatYaml from '../assets/schema/rules/sidecars/anat.yaml';
import funcYaml from '../assets/schema/rules/sidecars/func.yaml';
import fmapYaml from '../assets/schema/rules/sidecars/fmap.yaml';
import dwiYaml from '../assets/schema/rules/sidecars/dwi.yaml';
import aslYaml from '../assets/schema/rules/sidecars/asl.yaml';
import petYaml from '../assets/schema/rules/sidecars/pet.yaml';
import megYaml from '../assets/schema/rules/sidecars/meg.yaml';
import metadataInfo from '../assets/schema/rules/sidecars/metadata.yaml';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FieldDetails {
    display_name?: string;
    description?: string;
    type?: string;
    enum?: any[];
    anyOf?: { type: string; format?: string; items?: any }[];
    items?: { type: string };
    default_value?: any;
}

interface FieldItem {
    field: string;
    details: FieldDetails;
}

interface ConditionalFieldItem extends FieldItem {
    level: string;
    condition: string;
}

interface FieldsSections {
    required: FieldItem[];
    recommended: FieldItem[];
    optional: FieldItem[];
    conditional: ConditionalFieldItem[];
}

type ValidationError = string | null;

interface ValidationErrors {
    [field: string]: ValidationError;
}

interface ModalityFormProps {
    ss: any;
    ezbids: any;
    onFormSubmitted?: (ezbids: any) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const optionsBoolean = [
    { value: true, label: 'True' },
    { value: false, label: 'False' },
];

// ---------------------------------------------------------------------------
// Pure helper functions (ported from Vue methods with no `this` dependency)
// ---------------------------------------------------------------------------

function isNumeric(value: string): boolean {
    return /^-?\d+(\.\d+)?$/.test(value);
}

function getPlaceholderByType(type: string | undefined): string {
    if (type === 'string') return 'Enter string';
    if (type === 'number') return 'Enter number';
    if (type === 'integer') return 'Enter integer';
    if (type === 'boolean') return 'Select';
    if (type === 'array') return 'Enter array []';
    if (type === 'object') return 'Enter object {}';
    return '';
}

function formatType(type: string): string {
    return type.split(' ')[0];
}

function parseDefaultValue(type: string): any {
    if (type === 'string') return '';
    if (type === 'number') return null;
    if (type === 'integer') return null;
    if (type === 'boolean') return undefined;
    if (type === 'array') return [];
    if (type === 'object') return {};
    return '';
}

function setDefaultValue(details: { type?: any; anyOf?: any[] }): any {
    if (details.type != null) return parseDefaultValue(details.type);
    if (details?.anyOf?.length) {
        if (details.anyOf[0].type) return parseDefaultValue(details.anyOf[0].type);
        for (const item of details.anyOf) {
            if (item.type) return parseDefaultValue(item.type);
        }
        return '';
    }
    return '';
}

function parseType(details: { type?: any; anyOf?: any[] }): string {
    if (details.type != null) return details.type;
    if (details?.anyOf?.length) {
        if (details.anyOf[0].type) return details.anyOf[0].type;
        for (const item of details.anyOf) {
            if (item.type) return item.type;
        }
        return 'string';
    }
    return 'string';
}

function inputType(
    item: FieldItem
): 'select-type' | 'input' | 'input-number' | 'input-integer' | 'select-boolean' | 'select-enum' | undefined {
    if (item.details?.anyOf?.length) return 'select-type';
    if (
        (item.details.type === 'string' || item.details.type === 'object' || item.details.type === 'array') &&
        item.details.enum === undefined
    )
        return 'input';
    if (item.details.type === 'number') return 'input-number';
    if (item.details.type === 'integer') return 'input-integer';
    if (item.details.type === 'boolean') return 'select-boolean';
    if (item.details.enum) return 'select-enum';
    return undefined;
}

function parseOptionsEnum(enumArray: any[] | undefined): { value: any; label: string }[] {
    if (!enumArray) return [];
    return enumArray.map((item: any) => {
        if (typeof item === 'object') {
            if (item['$ref']) {
                const regex = /objects.enums.(\w+).value/;
                const refObject = regex.exec(item['$ref']);
                if (refObject) {
                    let val = refObject[1];
                    if (val.endsWith('Minus')) {
                        val = val.replace('Minus', '-');
                    }
                    return { value: val, label: val };
                }
            }
        }
        return { value: item, label: String(item) };
    });
}

function parseArrayValues(value: any, details: FieldDetails): any {
    if (details.items?.type === 'number') {
        if (value && value.length > 0)
            return value
                .toString()
                .split(',')
                .map((item: string) => Number(item));
    }
    return value;
}

function getArrayValidation(value: any, item: FieldItem): string | true {
    if (value == null || value === '' || value === undefined) return true;
    const strValue = String(value);
    if (strValue.includes('[') || strValue.includes(']')) {
        return 'No brackets, only comma separated values';
    }

    if (item.details.items?.type === 'number') {
        if (typeof value === 'string') {
            if (!isNaN(Number(value))) return true;
            if (value.includes(',')) {
                const parts = value.split(',');
                if (parts.every((p: string) => !isNaN(Number(p)))) return true;
                return 'Every item in the list should be a number';
            }
            return 'The value should be a number or a list of numbers separated by commas';
        }
        if (typeof value === 'number') return true;
        if (Array.isArray(value)) {
            if (value.length === 0) return true;
            if (value.length === 1 && value[0] === '') return true;
            if (value.every((v: any) => typeof v === 'number')) return true;
        }
        return 'The value should be a number or an array of numbers';
    }
    return true;
}

// ---------------------------------------------------------------------------
// Field metadata builder (mirrors getFieldsMetaData)
// ---------------------------------------------------------------------------

function getFieldsMetaData(type: string): FieldsSections {
    let fileObject: Record<string, any> = {};
    if (['perf/asl', 'perf/m0scan'].includes(type)) {
        fileObject = aslYaml as any;
    } else if (type.startsWith('pet')) {
        fileObject = petYaml as any;
    } else if (type.startsWith('func')) {
        fileObject = funcYaml as any;
    } else if (type.startsWith('dwi')) {
        fileObject = dwiYaml as any;
    } else if (type.startsWith('fmap')) {
        fileObject = fmapYaml as any;
    } else if (type.startsWith('anat')) {
        fileObject = anatYaml as any;
    } else if (type.startsWith('meg')) {
        fileObject = megYaml as any;
    }

    const result: FieldsSections = {
        required: [],
        recommended: [],
        optional: [],
        conditional: [],
    };

    for (const [section, data] of Object.entries(fileObject)) {
        const fields = (data as any).fields || {};
        for (const [field, metadata] of Object.entries(fields) as [string, any][]) {
            if (['IntendedFor', 'TaskName'].includes(field)) continue;

            if (type === 'fmap/epi' && ['EchoTime__fmap', 'EchoTime1', 'EchoTime2', 'Units'].includes(field)) continue;
            if (
                ['fmap/magnitude1', 'fmap/magnitude2'].includes(type) &&
                ['EchoTime__fmap', 'EchoTime1', 'EchoTime2', 'Units', 'TotalReadoutTime'].includes(field)
            )
                continue;
            if (type === 'fmap/phasediff' && ['EchoTime__fmap', 'Units', 'TotalReadoutTime'].includes(field)) continue;
            if (
                ['fmap/phase1', 'fmap/phase2'].includes(type) &&
                ['EchoTime1', 'EchoTime2', 'Units', 'TotalReadoutTime'].includes(field)
            )
                continue;
            if (
                type === 'fmap/fieldmap' &&
                ['EchoTime__fmap', 'EchoTime1', 'EchoTime2', 'TotalReadoutTime'].includes(field)
            )
                continue;
            if (type === 'perf/m0scan' && field !== 'RepetitionTimePreparation') continue;
            if (type === 'pet/blood' && !section.includes('Blood')) continue;
            if (type === 'pet/pet' && section.includes('Blood')) continue;
            if (type.startsWith('func') && ['VolumeTiming', 'Units'].includes(field)) continue;
            if (
                type === 'meg/meg' &&
                [
                    'AssociatedEmptyRoom',
                    'MEGCoordinateSystem',
                    'MEGCoordinateUnits',
                    'SoftwareFilters',
                    'HardwareFilters',
                    'HeadCoilCoordinates',
                    'AnatomicalLandmarkCoordinates',
                ].includes(field)
            )
                continue;

            const details: FieldDetails = { ...((metadataInfo as any)[field] || {}) };
            details.default_value = setDefaultValue(details);
            details.type = parseType(details);

            const fieldData: FieldItem = { field, details };

            if (metadata === 'required' && !result.required.some((i) => i.field === fieldData.field))
                result.required.push(fieldData);
            if (metadata === 'recommended' && !result.recommended.some((i) => i.field === fieldData.field))
                result.recommended.push(fieldData);
            if (metadata === 'optional' && !result.optional.some((i) => i.field === fieldData.field))
                result.optional.push(fieldData);

            const level = metadata?.level || '';
            if (level === 'required' && !result.required.some((i) => i.field === fieldData.field))
                result.required.push(fieldData);
            else if (level === 'recommended' && !result.recommended.some((i) => i.field === fieldData.field))
                result.recommended.push(fieldData);
            else if (level === 'optional' && !result.optional.some((i) => i.field === fieldData.field))
                result.optional.push(fieldData);

            const levelAddendum = metadata?.level_addendum || '';
            if (levelAddendum.includes('required if') || levelAddendum.includes('required when')) {
                const obj: ConditionalFieldItem = {
                    ...fieldData,
                    level: 'required',
                    condition: levelAddendum,
                };
                if (!result.conditional.some((i) => i.field === fieldData.field)) result.conditional.push(obj);
            } else if (levelAddendum.includes('recommended if') || levelAddendum.includes('recommended when')) {
                const obj: ConditionalFieldItem = {
                    ...fieldData,
                    level: 'recommended',
                    condition: levelAddendum,
                };
                if (!result.conditional.some((i) => i.field === fieldData.field)) result.conditional.push(obj);
            }
        }
    }

    // Remove fields in conditional from other sections
    result.required = result.required.filter((item) => !result.conditional.some((c) => c.field === item.field));
    result.recommended = result.recommended.filter((item) => !result.conditional.some((c) => c.field === item.field));
    result.optional = result.optional.filter((item) => !result.conditional.some((c) => c.field === item.field));

    return result;
}

// ---------------------------------------------------------------------------
// Validation engine
// ---------------------------------------------------------------------------

function validateNumericField(value: any, item: FieldItem, formData: Record<string, any>): ValidationError {
    if (!['number', 'integer'].includes(item.details?.type || '')) return null;
    const v = value ?? formData[item.field];
    const stringValue = `${v}`;
    if (stringValue === 'null' || stringValue === 'undefined' || stringValue === '') return null;
    if (item.details.type === 'array' && item.details.items?.type === 'number') {
        if (stringValue.includes(',')) {
            if (!stringValue.split(',').every((part: string) => isNumeric(part.trim()))) {
                return 'Please enter a valid number or a comma-separated list of numbers';
            }
        }
        return null;
    }
    if (!isNumeric(stringValue)) {
        return 'Please enter a valid number';
    }
    return null;
}

function validateArrayField(value: any, item: FieldItem): ValidationError {
    if (item.details?.type !== 'array') return null;
    const result = getArrayValidation(value, item);
    if (value != null && result !== true) return result as string;
    return null;
}

function validateConditionalField(
    value: any,
    item: ConditionalFieldItem,
    formData: Record<string, any>
): ValidationError {
    if (item.level !== 'required') return null;

    // `fieldName` is `true|false`
    let matches = item.condition.match(/`(\w+)`\s+is\s+`(true|false)`/i);
    if (matches) {
        const fieldName = matches[1];
        const expectedValue = matches[2];
        if (
            formData.hasOwnProperty(fieldName) &&
            formData[fieldName] === expectedValue &&
            expectedValue &&
            (value == null || value === '')
        ) {
            return `Required because ${fieldName} == ${expectedValue}`;
        }
    }

    // `fieldName` is defined as `value`
    matches = item.condition.match(/`(\w+)`\s+is\s+defined\s+as\s+`(\w+)`/i);
    if (matches) {
        const fieldName = matches[1];
        const expectedValue = matches[2];
        if (formData.hasOwnProperty(fieldName) && String(formData[fieldName]) === expectedValue && !value) {
            return `Required because ${fieldName} == ${expectedValue}`;
        }
    }

    // `fieldName` is `value`
    matches = item.condition.match(/`(\w+)`\s+is\s+`(\w+)`/i);
    if (matches) {
        const fieldName = matches[1];
        const expectedValue = matches[2];
        if (formData.hasOwnProperty(fieldName) && String(formData[fieldName]) === expectedValue && !value) {
            return `Required because ${fieldName} == ${expectedValue}`;
        }
    }

    // section.fields.field == 'value'
    matches = item.condition.match(/(\w+)\.fields\.(\w+)\s+==\s+['"]([\w-]+)['"]/i);
    if (matches) {
        const fieldName = matches[2];
        const expectedValue = matches[3];
        if (formData.hasOwnProperty(fieldName) && String(formData[fieldName]) === expectedValue && !value) {
            return `Required because ${fieldName} == ${expectedValue}`;
        }
    }

    // `fieldName` is `val1` or `val2`
    matches = item.condition.match(/`(\w+)`\s+is\s+`(\w+)`\s+or\s+`(\w+)`/);
    if (matches) {
        const fieldName = matches[1];
        const ev1 = matches[2];
        const ev2 = matches[3];
        if (
            formData.hasOwnProperty(fieldName) &&
            (String(formData[fieldName]) === ev1 || String(formData[fieldName]) === ev2) &&
            !value
        ) {
            return `Required because ${fieldName} == ${ev1} or ${ev2}`;
        }
    }

    // `fieldName` is in [`val1`,`val2`, ...]
    matches = item.condition.match(/`(\w+)`\s+is\s+in\s+\[(`([\w-]+)`(,\s*`([\w-]+)`)*\s*)+\]/);
    if (matches) {
        const fieldName = matches[1];
        const expectedValues = matches[2].split(',').map((v: string) => v.trim().replace(/`/g, ''));
        if (formData.hasOwnProperty(fieldName) && expectedValues.includes(String(formData[fieldName])) && !value) {
            return `Required because ${fieldName} == ${expectedValues.join(' or ')}`;
        }
    }

    return null;
}

function runValidation(fields: FieldsSections, formData: Record<string, any>): ValidationErrors {
    const errors: ValidationErrors = {};

    // Required fields
    fields.required.forEach((item) => {
        const val = formData[item.field];
        if (val === null || val === undefined || val === '') {
            errors[item.field] = `${item.field} is required`;
            return;
        }
        const numErr = validateNumericField(val, item, formData);
        if (numErr) {
            errors[item.field] = numErr;
            return;
        }
        const arrErr = validateArrayField(val, item);
        if (arrErr) {
            errors[item.field] = arrErr;
            return;
        }
    });

    // Recommended fields
    fields.recommended.forEach((item) => {
        const val = formData[item.field];
        const numErr = validateNumericField(val, item, formData);
        if (numErr) {
            errors[item.field] = numErr;
            return;
        }
        const arrErr = validateArrayField(val, item);
        if (arrErr) {
            errors[item.field] = arrErr;
            return;
        }
    });

    // Optional fields
    fields.optional.forEach((item) => {
        const val = formData[item.field];
        const numErr = validateNumericField(val, item, formData);
        if (numErr) {
            errors[item.field] = numErr;
            return;
        }
        const arrErr = validateArrayField(val, item);
        if (arrErr) {
            errors[item.field] = arrErr;
            return;
        }
    });

    // Conditional fields
    fields.conditional.forEach((item) => {
        const val = formData[item.field];
        const condErr = validateConditionalField(val, item, formData);
        if (condErr) {
            errors[item.field] = condErr;
            return;
        }
        const numErr = validateNumericField(val, item, formData);
        if (numErr) {
            errors[item.field] = numErr;
            return;
        }
        const arrErr = validateArrayField(val, item);
        if (arrErr) {
            errors[item.field] = arrErr;
            return;
        }
    });

    return errors;
}

// ---------------------------------------------------------------------------
// Tooltip component (lightweight title-based)
// ---------------------------------------------------------------------------

function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
    return (
        <span title={text} className="cursor-help">
            {children}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Info icon (replaces font-awesome info-circle)
// ---------------------------------------------------------------------------

function InfoIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 512 512"
            className="inline-block w-3.5 h-3.5 ml-1 text-blue-500 fill-current"
        >
            <path d="M256 8C119.043 8 8 119.083 8 256c0 136.997 111.043 248 248 248s248-111.003 248-248C504 119.083 392.957 8 256 8zm0 110c23.196 0 42 18.804 42 42s-18.804 42-42 42-42-18.804-42-42 18.804-42 42-42zm56 254c0 6.627-5.373 12-12 12h-88c-6.627 0-12-5.373-12-12v-24c0-6.627 5.373-12 12-12h12v-64h-12c-6.627 0-12-5.373-12-12v-24c0-6.627 5.373-12 12-12h64c6.627 0 12 5.373 12 12v100h12c6.627 0 12 5.373 12 12v24z" />
        </svg>
    );
}

// ---------------------------------------------------------------------------
// FieldLabel sub-component
// ---------------------------------------------------------------------------

function FieldLabel({ item }: { item: FieldItem }) {
    return (
        <label className="block mb-1 text-xs font-medium text-gray-700">
            {item.details.display_name}
            <Tooltip text={item.details.description || ''}>
                <InfoIcon />
            </Tooltip>
        </label>
    );
}

// ---------------------------------------------------------------------------
// FieldInput sub-component
// ---------------------------------------------------------------------------

interface FieldInputProps {
    item: FieldItem;
    value: any;
    onChange: (field: string, value: any) => void;
    error: ValidationError;
    onTypeChange?: (item: FieldItem, newType: string) => void;
}

function FieldInput({ item, value, onChange, error, onTypeChange }: FieldInputProps) {
    const type = inputType(item);
    const displayValue = value ?? '';

    const baseInputClass =
        'w-full rounded border px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400';
    const errorBorderClass = error ? 'border-red-400' : 'border-gray-300';

    switch (type) {
        case 'input':
            return (
                <input
                    type="text"
                    className={`${baseInputClass} ${errorBorderClass}`}
                    value={typeof displayValue === 'object' ? JSON.stringify(displayValue) : String(displayValue)}
                    placeholder={getPlaceholderByType(item.details.type)}
                    onChange={(e) => onChange(item.field, e.target.value)}
                />
            );

        case 'input-number':
            return (
                <input
                    type="text"
                    inputMode="decimal"
                    className={`${baseInputClass} ${errorBorderClass}`}
                    value={String(displayValue)}
                    placeholder={getPlaceholderByType(item.details.type)}
                    onChange={(e) => onChange(item.field, e.target.value)}
                />
            );

        case 'input-integer':
            return (
                <input
                    type="text"
                    inputMode="numeric"
                    className={`${baseInputClass} ${errorBorderClass}`}
                    value={String(displayValue)}
                    placeholder={getPlaceholderByType(item.details.type)}
                    onChange={(e) => onChange(item.field, e.target.value)}
                />
            );

        case 'select-boolean':
            return (
                <select
                    className={`${baseInputClass} ${errorBorderClass}`}
                    value={String(displayValue)}
                    onChange={(e) => {
                        const v = e.target.value;
                        onChange(item.field, v === 'true' ? true : v === 'false' ? false : undefined);
                    }}
                >
                    <option value="">Select</option>
                    {optionsBoolean.map((opt) => (
                        <option key={String(opt.value)} value={String(opt.value)}>
                            {opt.label}
                        </option>
                    ))}
                </select>
            );

        case 'select-enum': {
            const options = parseOptionsEnum(item.details.enum);
            return (
                <select
                    className={`${baseInputClass} ${errorBorderClass}`}
                    value={String(displayValue)}
                    onChange={(e) => onChange(item.field, e.target.value)}
                >
                    <option value="">Select</option>
                    {options.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                            {opt.label}
                        </option>
                    ))}
                </select>
            );
        }

        case 'select-type': {
            const ft = formatType(item.details.type || 'string');
            return (
                <div className="flex gap-1">
                    <div className="flex-1">
                        {(ft === 'string' || ft === 'object' || ft === 'array') && (
                            <input
                                type="text"
                                className={`${baseInputClass} ${errorBorderClass}`}
                                value={
                                    typeof displayValue === 'object'
                                        ? JSON.stringify(displayValue)
                                        : String(displayValue)
                                }
                                placeholder={getPlaceholderByType(ft)}
                                onChange={(e) => onChange(item.field, e.target.value)}
                            />
                        )}
                        {ft === 'number' && (
                            <input
                                type="text"
                                inputMode="decimal"
                                className={`${baseInputClass} ${errorBorderClass}`}
                                value={String(displayValue)}
                                placeholder={getPlaceholderByType(ft)}
                                onChange={(e) => onChange(item.field, e.target.value)}
                            />
                        )}
                        {ft === 'integer' && (
                            <input
                                type="text"
                                inputMode="numeric"
                                className={`${baseInputClass} ${errorBorderClass}`}
                                value={String(displayValue)}
                                placeholder={getPlaceholderByType(ft)}
                                onChange={(e) => onChange(item.field, e.target.value)}
                            />
                        )}
                    </div>
                    <div className="w-1/3">
                        <select
                            className={`${baseInputClass} border-gray-300`}
                            value={item.details.type || ''}
                            onChange={(e) => onTypeChange?.(item, e.target.value)}
                        >
                            <option value="">Select Type</option>
                            {(item.details.anyOf || []).map((typeOption, idx) => {
                                const label = typeOption.format
                                    ? `${typeOption.type} (${typeOption.format})`
                                    : typeOption.type;
                                return (
                                    <option key={idx} value={label}>
                                        {label}
                                    </option>
                                );
                            })}
                        </select>
                    </div>
                </div>
            );
        }

        default:
            return null;
    }
}

// ---------------------------------------------------------------------------
// Section column sub-component
// ---------------------------------------------------------------------------

interface SectionColumnProps {
    title: string;
    bgClass: string;
    items: FieldItem[];
    formData: Record<string, any>;
    errors: ValidationErrors;
    onChange: (field: string, value: any) => void;
    onTypeChange: (item: FieldItem, newType: string) => void;
}

function SectionColumn({ title, bgClass, items, formData, errors, onChange, onTypeChange }: SectionColumnProps) {
    return (
        <div className={`flex-1 rounded pl-2.5 pr-1 py-2 ${bgClass}`}>
            <h3 className="text-center font-semibold mb-2">{title}</h3>
            {items.map((item, index) => (
                <div key={`${title}-${index}`} className="mt-5">
                    <FieldLabel item={item} />
                    <FieldInput
                        item={item}
                        value={formData[item.field]}
                        onChange={onChange}
                        error={errors[item.field] || null}
                        onTypeChange={onTypeChange}
                    />
                    {errors[item.field] && <p className="text-red-500 text-xs mt-0.5">{errors[item.field]}</p>}
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ModalityForm({ ss, ezbids, onFormSubmitted }: ModalityFormProps) {
    const [showDialog, setShowDialog] = useState(false);
    const [formData, setFormData] = useState<Record<string, any>>({});
    const [fields, setFields] = useState<FieldsSections>({
        required: [],
        recommended: [],
        optional: [],
        conditional: [],
    });
    const [errors, setErrors] = useState<ValidationErrors>({});

    // We keep a ref to the latest formData so callbacks can read it synchronously
    const formDataRef = useRef(formData);
    formDataRef.current = formData;

    const fieldsRef = useRef(fields);
    fieldsRef.current = fields;

    // --------------------------------------------------
    // Validate whenever formData or fields change
    // --------------------------------------------------

    useEffect(() => {
        if (showDialog) {
            setErrors(runValidation(fields, formData));
        }
    }, [formData, fields, showDialog]);

    // --------------------------------------------------
    // Handle field value changes
    // --------------------------------------------------

    const handleChange = useCallback((field: string, value: any) => {
        setFormData((prev) => ({ ...prev, [field]: value }));
    }, []);

    // --------------------------------------------------
    // Handle anyOf type selector change
    // --------------------------------------------------

    const handleTypeChange = useCallback((item: FieldItem, newValue: string) => {
        const extractedData = item.details.anyOf?.find((opt) => opt.type === newValue);
        const updatedDetails = { ...item.details, type: newValue };
        if (extractedData?.items) {
            updatedDetails.items = extractedData.items;
        }

        // Update the fields state with the new details
        setFields((prev) => {
            const updateSection = (arr: FieldItem[]) =>
                arr.map((fi) => (fi.field === item.field ? { ...fi, details: updatedDetails } : fi));
            return {
                required: updateSection(prev.required),
                recommended: updateSection(prev.recommended),
                optional: updateSection(prev.optional),
                conditional: prev.conditional.map((fi) =>
                    fi.field === item.field ? { ...fi, details: updatedDetails } : fi
                ),
            };
        });
    }, []);

    // --------------------------------------------------
    // Load initial form values from ezbids objects
    // --------------------------------------------------

    const loadInitFormValues = useCallback(
        (fd: Record<string, any>): Record<string, any> => {
            const result = { ...fd };
            ezbids.objects.forEach((file: any) => {
                if (file.series_idx === ss.series_idx) {
                    file.items.forEach((item: any) => {
                        if (item.name.includes('json') && item.sidecar_json) {
                            const json = JSON.parse(item.sidecar_json);
                            for (const [key, value] of Object.entries(json)) {
                                if (result.hasOwnProperty(key)) result[key] = value;
                            }
                        }
                    });
                }
            });
            return result;
        },
        [ezbids, ss]
    );

    // --------------------------------------------------
    // Create JSON output (mirrors createJSONOutput)
    // --------------------------------------------------

    const createJSONOutput = useCallback(() => {
        const currentFormData = formDataRef.current;
        const currentFields = fieldsRef.current;

        ezbids.objects.forEach((file: any) => {
            if (file.series_idx === ss.series_idx) {
                file.items.forEach((item: any) => {
                    if (item.name.includes('json') && item.sidecar_json) {
                        const json = JSON.parse(item.sidecar_json);
                        for (const [key, value] of Object.entries(currentFormData) as [string, any][]) {
                            const details = (Object.values(currentFields) as FieldItem[][])
                                .flat()
                                .find((fi: FieldItem) => fi.field === key)?.details;
                            const fieldType = details?.type;

                            if (
                                value !== null &&
                                value !== '' &&
                                value !== undefined &&
                                !(Array.isArray(value) && value.length === 1 && value[0] === '')
                            ) {
                                if (fieldType === 'string') value = String(value).replace(/"/g, '');
                                if (fieldType === 'number') value = Number(value);
                                if (fieldType === 'integer') value = Number(value);
                                if (fieldType === 'boolean') value = Boolean(value);
                                if (fieldType === 'array') {
                                    value = parseArrayValues(value, details!);
                                    if (Array.isArray(value) && value.length === 0) continue;
                                }
                                if (fieldType === 'object') value = JSON.parse(value);
                                json[key] = value;
                            }
                        }
                        item.sidecar_json = JSON.stringify(json, null, 2);
                    }
                });
            }
        });
    }, [ezbids, ss]);

    // --------------------------------------------------
    // Init form (opens dialog)
    // --------------------------------------------------

    const initForm = useCallback(() => {
        const typeStr = ss.type || ss._type;
        let newFields = getFieldsMetaData(typeStr);

        // Build initial formData with default values
        let fd: Record<string, any> = {};
        for (const section of Object.values(newFields) as FieldItem[][]) {
            section.forEach((item: FieldItem) => {
                fd[item.field] = item.details.default_value ?? undefined;
            });
        }

        // Load existing values from ezbids
        fd = (() => {
            const result = { ...fd };
            ezbids.objects.forEach((file: any) => {
                if (file.series_idx === ss.series_idx) {
                    file.items.forEach((item: any) => {
                        if (item.name.includes('json') && item.sidecar_json) {
                            const json = JSON.parse(item.sidecar_json);
                            for (const [key, value] of Object.entries(json)) {
                                if (result.hasOwnProperty(key)) result[key] = value;
                            }
                        }
                    });
                }
            });
            return result;
        })();

        // ASL-specific field removal
        if (typeStr === 'perf/asl' && ['CASL', 'PCASL'].includes(fd['ArterialSpinLabelingType'])) {
            const badKeys = [
                'PASLType',
                'LabelingSlabThickness',
                'BolusCutOffFlag',
                'BolusCutOffTimingSequence',
                'BolusCutOffDelayTime',
                'BolusCutOffTechnique',
            ];

            const removeByField = (arr: any[], badKey: string) => arr.filter((obj: any) => obj.field !== badKey);

            for (const badKey of badKeys) {
                newFields = {
                    required: removeByField(newFields.required, badKey),
                    recommended: removeByField(newFields.recommended, badKey),
                    optional: removeByField(newFields.optional, badKey),
                    conditional: removeByField(newFields.conditional, badKey) as ConditionalFieldItem[],
                };
                if (fd.hasOwnProperty(badKey)) {
                    delete fd[badKey];
                }
            }
        }

        setFormData(fd);
        setFields(newFields);
        setShowDialog(true);
    }, [ss, ezbids, loadInitFormValues]);

    // --------------------------------------------------
    // Submit handler
    // --------------------------------------------------

    const handleSubmit = useCallback(() => {
        const validationErrors = runValidation(fieldsRef.current, formDataRef.current);
        const hasRequiredErrors = fieldsRef.current.required.some((item) => !!validationErrors[item.field]);
        if (hasRequiredErrors) {
            window.alert('Please fill all the required fields');
        }
        createJSONOutput();
        setShowDialog(false);
        onFormSubmitted?.(ezbids);
    }, [createJSONOutput, ezbids, onFormSubmitted]);

    // --------------------------------------------------
    // Render
    // --------------------------------------------------

    return (
        <>
            <button
                type="button"
                onClick={initForm}
                className="rounded bg-white border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
            >
                Edit Metadata
            </button>

            <Dialog.Root open={showDialog} onOpenChange={setShowDialog}>
                <Dialog.Portal>
                    <Dialog.Overlay className="fixed inset-0 bg-black/40 z-40" />
                    <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[90vw] max-w-6xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg bg-white p-6 shadow-xl focus:outline-none">
                        <Dialog.Title className="text-lg font-bold mb-4">Relevant Metadata</Dialog.Title>

                        {/* Three-column layout: required | recommended | optional+conditional */}
                        <div className="flex gap-2">
                            {/* Required */}
                            <SectionColumn
                                title="Required"
                                bgClass="bg-blue-50"
                                items={fields.required}
                                formData={formData}
                                errors={errors}
                                onChange={handleChange}
                                onTypeChange={handleTypeChange}
                            />

                            {/* Recommended */}
                            <SectionColumn
                                title="Recommended"
                                bgClass="bg-indigo-50"
                                items={fields.recommended}
                                formData={formData}
                                errors={errors}
                                onChange={handleChange}
                                onTypeChange={handleTypeChange}
                            />

                            {/* Optional + Conditional */}
                            <div className="flex-1 rounded pl-2.5 pr-1 py-2 bg-blue-50">
                                <h3 className="text-center font-semibold mb-2">Optional</h3>
                                {fields.optional.map((item, index) => (
                                    <div key={`optional-${index}`} className="mt-5">
                                        <FieldLabel item={item} />
                                        <FieldInput
                                            item={item}
                                            value={formData[item.field]}
                                            onChange={handleChange}
                                            error={errors[item.field] || null}
                                            onTypeChange={handleTypeChange}
                                        />
                                        {errors[item.field] && (
                                            <p className="text-red-500 text-xs mt-0.5">{errors[item.field]}</p>
                                        )}
                                    </div>
                                ))}

                                {/* Conditional fields rendered under Optional */}
                                {fields.conditional.map((item, index) => (
                                    <div key={`conditional-${index}`} className="mt-5">
                                        <FieldLabel item={item} />
                                        <FieldInput
                                            item={item}
                                            value={formData[item.field]}
                                            onChange={handleChange}
                                            error={errors[item.field] || null}
                                            onTypeChange={handleTypeChange}
                                        />
                                        {errors[item.field] && (
                                            <p className="text-red-500 text-xs mt-0.5">{errors[item.field]}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                        <br />

                        {/* Footer buttons */}
                        <div className="flex justify-end gap-2 mt-4">
                            <Dialog.Close asChild>
                                <button
                                    type="button"
                                    className="rounded border border-gray-300 bg-white px-4 py-2 text-sm hover:bg-gray-50"
                                >
                                    Cancel
                                </button>
                            </Dialog.Close>
                            <button
                                type="button"
                                onClick={handleSubmit}
                                className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                            >
                                Submit
                            </button>
                        </div>
                    </Dialog.Content>
                </Dialog.Portal>
            </Dialog.Root>
        </>
    );
}
