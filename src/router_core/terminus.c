/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 * 
 *   http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

#include "router_core_private.h"

struct qdr_terminus_t {
    qdr_field_t            *address;
    pn_durability_t         durability;
    pn_expiry_policy_t      expiry_policy;
    pn_seconds_t            timeout;
    bool                    dynamic;
    pn_distribution_mode_t  distribution_mode;
    pn_data_t              *properties;
    pn_data_t              *filter;
    pn_data_t              *outcomes;
    pn_data_t              *capabilities;
};

ALLOC_DECLARE(qdr_terminus_t);
ALLOC_DEFINE(qdr_terminus_t);

qdr_terminus_t *qdr_terminus(pn_terminus_t *pn)
{
    qdr_terminus_t *term = new_qdr_terminus_t();
    ZERO(term);

    term->properties   = pn_data(0);
    term->filter       = pn_data(0);
    term->outcomes     = pn_data(0);
    term->capabilities = pn_data(0);

    if (pn) {
        const char *addr = pn_terminus_get_address(pn);
        if (addr && *addr)
            term->address = qdr_field(addr);

        term->durability        = pn_terminus_get_durability(pn);
        term->expiry_policy     = pn_terminus_get_expiry_policy(pn);
        term->timeout           = pn_terminus_get_timeout(pn);
        term->dynamic           = pn_terminus_is_dynamic(pn);
        term->distribution_mode = pn_terminus_get_distribution_mode(pn);

        pn_data_copy(term->properties,   pn_terminus_properties(pn));
        pn_data_copy(term->filter,       pn_terminus_filter(pn));
        pn_data_copy(term->outcomes,     pn_terminus_outcomes(pn));
        pn_data_copy(term->capabilities, pn_terminus_capabilities(pn));
    }

    return term;
}


void qdr_terminus_free(qdr_terminus_t *term)
{
    if (term == 0)
        return;

    qdr_field_free(term->address);
    pn_data_free(term->properties);
    pn_data_free(term->filter);
    pn_data_free(term->outcomes);
    pn_data_free(term->capabilities);

    free_qdr_terminus_t(term);
}


void qdr_terminus_copy(qdr_terminus_t *from, pn_terminus_t *to)
{
    if (!from)
        return;

    if (from->address) {
        qd_iterator_reset_view(from->address->iterator, ITER_VIEW_ALL);
        unsigned char *addr = qd_iterator_copy(from->address->iterator);
        pn_terminus_set_address(to, (char*) addr);
        free(addr);
    }

    pn_terminus_set_durability(to,        from->durability);
    pn_terminus_set_expiry_policy(to,     from->expiry_policy);
    pn_terminus_set_timeout(to,           from->timeout);
    pn_terminus_set_dynamic(to,           from->dynamic);
    pn_terminus_set_distribution_mode(to, from->distribution_mode);

    pn_data_copy(pn_terminus_properties(to),   from->properties);
    pn_data_copy(pn_terminus_filter(to),       from->filter);
    pn_data_copy(pn_terminus_outcomes(to),     from->outcomes);
    pn_data_copy(pn_terminus_capabilities(to), from->capabilities);
}


void qdr_terminus_add_capability(qdr_terminus_t *term, const char *capability)
{
    pn_data_put_symbol(term->capabilities, pn_bytes(strlen(capability), capability));
}


bool qdr_terminus_has_capability(qdr_terminus_t *term, const char *capability)
{
    pn_data_t *cap = term->capabilities;
    pn_data_rewind(cap);
    pn_data_next(cap);
    if (cap && pn_data_type(cap) == PN_SYMBOL) {
        pn_bytes_t sym = pn_data_get_symbol(cap);
        if (sym.size == strlen(capability) && strcmp(sym.start, capability) == 0)
            return true;
    }

    return false;
}


bool qdr_terminus_is_anonymous(qdr_terminus_t *term)
{
    return term == 0 || term->address == 0;
}


bool qdr_terminus_is_dynamic(qdr_terminus_t *term)
{
    return term->dynamic;
}


void qdr_terminus_set_address(qdr_terminus_t *term, const char *addr)
{
    qdr_field_free(term->address);
    term->address = qdr_field(addr);
}


qd_iterator_t *qdr_terminus_get_address(qdr_terminus_t *term)
{
    if (qdr_terminus_is_anonymous(term))
        return 0;

    return term->address->iterator;
}


qd_iterator_t *qdr_terminus_dnp_address(qdr_terminus_t *term)
{
    pn_data_t *props = term->properties;

    if (!props)
        return 0;

    pn_data_rewind(props);
    if (pn_data_next(props) && pn_data_enter(props) && pn_data_next(props)) {
        pn_bytes_t sym = pn_data_get_symbol(props);
        if (sym.start && strcmp(QD_DYNAMIC_NODE_PROPERTY_ADDRESS, sym.start) == 0) {
            if (pn_data_next(props)) {
                pn_bytes_t val = pn_data_get_string(props);
                if (val.start && *val.start != '\0')
                    return qd_iterator_binary(val.start, val.size, ITER_VIEW_ALL);
            }
        }
    }

    return 0;
}


