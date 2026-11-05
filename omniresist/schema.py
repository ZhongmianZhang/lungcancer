"""Strict contract for professionally curated reports, not raw sequencing data."""
from __future__ import annotations

import copy
import math
import re

from jakstat.engine import egfr_context_confirmed
from rasmapk.engine import validate_input as validate_context

GENOMIC = {'snv', 'indel', 'amplification', 'deletion', 'fusion', 'splice', 'structural', 'noncoding', 'ecDNA'}
READOUTS = {'methylation', 'accessibility', 'histone_mark', 'expression', 'protein', 'signature'}
KINDS = GENOMIC | READOUTS
DNA_CAP = GENOMIC - {'signature'}
CAPABILITIES = {
    'target_dna': DNA_CAP - {'ecDNA'}, 'wes': DNA_CAP - {'ecDNA', 'noncoding'}, 'wgs': DNA_CAP,
    'long_read_dna': DNA_CAP | {'methylation'},
    'rna': {'fusion', 'splice', 'expression', 'signature'},
    'methylation': {'methylation', 'signature'},
    'atac': {'accessibility', 'signature'}, 'chip_seq': {'histone_mark', 'signature'},
    'scrna': {'expression', 'signature', 'fusion', 'splice'},
    'scatac': {'accessibility', 'signature'},
    'spatial': {'expression', 'signature', 'protein'}, 'protein': {'protein', 'expression'},
}
ASSAY_FLAGS = {'negative_result', 'sensitivity_characterized', 'matched_normal_available',
               'paired_wbc_available', 'rna_quality_passed', 'compartment_resolved',
               'genome_coverage_evaluated', 'native_modification_validated'}
FINDING_FLAGS = {'orthogonal_confirmed', 'locus_coverage_confirmed', 'compartment_confirmed',
                 'rna_confirmed', 'in_frame', 'kinase_domain_retained', 'ploidy_reviewed',
                 'focal_amplification', 'baseline_comparison_confirmed', 'phase_confirmed',
                 'egfr_clonal_link_confirmed', 'original_egfr_driver'}
FUNCTION_FLAGS = {'patient_matched_progression', 'selective_target_engagement', 'orthogonal_perturbation',
                  'rescue_or_reconstitution', 'downstream_axis_measured', 'resistance_phenotype_measured',
                  'malignant_compartment_resolved'}


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value)


def booleans(row, fields):
    for key in fields:
        if key in row and type(row[key]) is not bool:
            raise ValueError(key + ' must be a JSON boolean')


def text(row, fields, limit=2000):
    for key in fields:
        row.setdefault(key, '')
        if not isinstance(row[key], str) or len(row[key]) > limit:
            raise ValueError(key + ' must be a short string')


def enum(row, key, options, default='unknown'):
    row.setdefault(key, default)
    if not isinstance(row[key], str) or row[key] not in options:
        raise ValueError('Invalid ' + key)


def fraction(row, fields):
    for key in fields:
        if key not in row:
            continue
        value = row[key]
        if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(key + ' must be a finite fraction from 0 to 1, not percent')


def validate_input(document):
    if not isinstance(document, dict) or set(document) - {'schema_version', 'case_label', 'context', 'assays', 'findings', 'functional_tests'}:
        raise ValueError('Unknown top-level fields')
    if document.get('schema_version') != '1.0' or not isinstance(document.get('context'), dict):
        raise ValueError('schema_version 1.0 and context object are required')
    data = copy.deepcopy(document)
    ctx = data['context']; confirmed = ctx.pop('egfr_driver_confirmed', False)
    if type(confirmed) is not bool:
        raise ValueError('egfr_driver_confirmed must be boolean')
    base = {'schema_version': '1.0', 'context': ctx, 'findings': []}
    if 'case_label' in data:
        base['case_label'] = data['case_label']
    data['context'] = validate_context(base)['context']
    data['context']['egfr_driver_confirmed'] = confirmed
    if confirmed and not egfr_context_confirmed(data['context']):
        raise ValueError('Confirmed driver conflicts with missing or negative EGFR annotation')
    assays = data.get('assays')
    if not isinstance(assays, list) or not 1 <= len(assays) <= 50:
        raise ValueError('Provide 1 to 50 curated assays')
    seen = set()
    for a in assays:
        fields = {'id', 'platform_name', 'platform_version', 'modality', 'sample_type', 'collection_timing',
                  'status', 'validated_classes', 'tumor_fraction', 'tumor_fraction_method', 'lod_vaf',
                  'validated_min_tumor_fraction', 'quality_notes', 'target_scope'} | ASSAY_FLAGS
        if not isinstance(a, dict) or set(a) - fields or not identifier(a.get('id')) or a['id'] in seen:
            raise ValueError('Assay fields/ID invalid or duplicate')
        seen.add(a['id'])
        enum(a, 'modality', set(CAPABILITIES))
        enum(a, 'sample_type', {'tissue', 'plasma', 'csf', 'blood_cells', 'model', 'unknown'})
        enum(a, 'collection_timing', {'at_progression', 'before_progression', 'unknown'})
        enum(a, 'status', {'passed', 'failed', 'partial', 'unknown'})
        classes = a.get('validated_classes')
        if not isinstance(classes, list) or any(not isinstance(x, str) or x not in CAPABILITIES[a['modality']] for x in classes) or len(classes) != len(set(classes)):
            raise ValueError('Assay validated_classes must be unique and physically compatible with modality')
        booleans(a, ASSAY_FLAGS)
        fraction(a, {'tumor_fraction', 'lod_vaf', 'validated_min_tumor_fraction'})
        text(a, {'platform_name', 'platform_version', 'tumor_fraction_method', 'quality_notes', 'target_scope'})
        if not a['platform_name'].strip() or not a['platform_version'].strip():
            raise ValueError('Platform name and version must be supplied, or explicitly labelled unknown')
        if 'tumor_fraction' in a and not a['tumor_fraction_method'].strip():
            raise ValueError('Tumor fraction requires its estimation method')
        if a['modality'] == 'long_read_dna' and 'methylation' in classes and a.get('native_modification_validated') is not True:
            raise ValueError('Native long-read methylation requires a separately validated modification assay')
    findings = data.get('findings')
    if not isinstance(findings, list) or len(findings) > 300:
        raise ValueError('findings must be a list with at most 300 curated records')
    fseen = set()
    for f in findings:
        fields = {'id', 'assay_id', 'gene', 'alteration_type', 'variant', 'classification', 'tumor_origin',
                  'tumor_origin_evidence', 'compartment', 'acquisition', 'functional_direction', 'vaf',
                  'supporting_assay_ids', 'allele_phase', 'phase_partner', 'notes', 'egfr_clonal_link_evidence'} | FINDING_FLAGS
        if not isinstance(f, dict) or set(f) - fields or not identifier(f.get('id')) or f['id'] in fseen:
            raise ValueError('Finding fields/ID invalid or duplicate')
        fseen.add(f['id'])
        if not isinstance(f.get('assay_id'), str) or f['assay_id'] not in seen:
            raise ValueError('Finding assay_id must resolve')
        if not isinstance(f.get('gene'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,30}', f['gene']):
            raise ValueError('A curated gene or signature label is required')
        f['gene'] = f['gene'].upper()
        enum(f, 'alteration_type', KINDS)
        enum(f, 'classification', {'pathogenic', 'likely_pathogenic', 'vus', 'benign', 'likely_benign', 'unknown'})
        enum(f, 'tumor_origin', {'confirmed', 'unconfirmed', 'hematopoietic', 'germline', 'unknown'})
        enum(f, 'compartment', {'malignant', 'immune', 'stromal', 'mixed', 'unknown'})
        enum(f, 'acquisition', {'acquired', 'baseline', 'unknown'})
        enum(f, 'functional_direction', {'gain', 'loss', 'unknown'})
        enum(f, 'allele_phase', {'cis', 'trans', 'unresolved', 'not_applicable', 'unknown'})
        text(f, {'variant', 'tumor_origin_evidence', 'phase_partner', 'notes', 'egfr_clonal_link_evidence'})
        booleans(f, FINDING_FLAGS); fraction(f, {'vaf'})
        if f.get('original_egfr_driver') is True and f['gene'] != 'EGFR':
            raise ValueError('original_egfr_driver applies only to EGFR')
        if f.get('vaf') == 0:
            raise ValueError('A positive curated finding cannot carry zero VAF; use assay negative_result instead')
        f.setdefault('supporting_assay_ids', [])
        links = f['supporting_assay_ids']
        if not isinstance(links, list) or any(not isinstance(x, str) or x not in seen for x in links) or len(links) != len(set(links)):
            raise ValueError('Supporting assay links must be unique and resolve')
    tests = data.setdefault('functional_tests', [])
    if not isinstance(tests, list) or len(tests) > 50:
        raise ValueError('At most 50 functional tests')
    tseen = set()
    for t in tests:
        if not isinstance(t, dict) or set(t) - ({'id', 'finding_ids', 'result', 'description'} | FUNCTION_FLAGS) or not identifier(t.get('id')) or t['id'] in tseen:
            raise ValueError('Functional test fields/ID invalid or duplicate')
        tseen.add(t['id'])
        links = t.get('finding_ids')
        if not isinstance(links, list) or not links or any(not isinstance(x, str) or x not in fseen for x in links) or len(links) != len(set(links)):
            raise ValueError('Functional test links must be nonempty, unique and resolve')
        enum(t, 'result', {'supports_dependency', 'does_not_support', 'unknown'})
        booleans(t, FUNCTION_FLAGS); text(t, {'description'})
    return data
