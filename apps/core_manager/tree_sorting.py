import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


MAX_TREE_DEPTH = 20


def build_tree_nodes(items, label_getter, change_url_name):
    children_map = {}

    for item in items:
        children_map.setdefault(item.parent_id, []).append(item)

    for children in children_map.values():
        children.sort(key=lambda item: (item.sort_order, item.pk))

    visited = set()

    def build_branch(parent_id=None, depth=0):
        if depth > MAX_TREE_DEPTH:
            return []

        nodes = []
        for item in children_map.get(parent_id, []):
            if item.pk in visited:
                continue

            visited.add(item.pk)
            nodes.append({
                "id": item.pk,
                "label": label_getter(item),
                "change_url": reverse(change_url_name, args=[item.pk]),
                "children": build_branch(item.pk, depth + 1),
            })
        return nodes

    nodes = build_branch()

    for item in items:
        if item.pk not in visited:
            visited.add(item.pk)
            nodes.append({
                "id": item.pk,
                "label": label_getter(item),
                "change_url": reverse(change_url_name, args=[item.pk]),
                "children": build_branch(item.pk, 1),
            })

    return nodes


def parse_tree_request(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(_("Invalid JSON payload.")) from error

    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise ValidationError(_("Tree must be a list."))

    return payload, tree


def flatten_tree(tree, expected_ids, scope_validator=None):
    ordered_rows = []
    seen_ids = set()

    def visit(nodes, parent_id=None, depth=0):
        if depth > MAX_TREE_DEPTH:
            raise ValidationError(_("Maximum tree depth exceeded."))

        if not isinstance(nodes, list):
            raise ValidationError(_("Invalid tree node list."))

        for position, node in enumerate(nodes, start=1):
            if not isinstance(node, dict):
                raise ValidationError(_("Invalid tree node."))

            try:
                item_id = int(node.get("id"))
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Invalid tree item id.")) from error

            if item_id not in expected_ids:
                raise ValidationError(_("Tree contains an unknown item."))
            if item_id in seen_ids:
                raise ValidationError(_("Tree contains a duplicate item."))
            if scope_validator:
                scope_validator(item_id, parent_id)

            seen_ids.add(item_id)
            ordered_rows.append((item_id, parent_id, position))
            visit(node.get("children", []), item_id, depth + 1)

    visit(tree)

    if seen_ids != expected_ids:
        raise ValidationError(_("Tree must contain every item exactly once."))

    return ordered_rows


@transaction.atomic
def apply_tree_order(model, ordered_rows):
    objects = model.objects.in_bulk(item_id for item_id, _parent_id, _position in ordered_rows)
    changed = []

    for item_id, parent_id, position in ordered_rows:
        obj = objects[item_id]
        obj.parent_id = parent_id
        obj.sort_order = position
        changed.append(obj)

    model.objects.bulk_update(changed, ["parent", "sort_order"])
    return len(changed)
