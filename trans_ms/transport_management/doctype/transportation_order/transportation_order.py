# Copyright (c) 2021, Aakvatech Limited and contributors
# For license information, please see license.txt

import frappe
import time
import datetime
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate
from frappe.model.naming import make_autoname
from trans_ms.utlis.dimension import set_dimension

class TransportationOrder(Document):

    def validate(self):
        if self.customer:
            currency = frappe.get_value("Customer", self.customer, "default_currency")
            if currency:
                for row in self.assign_transport:
                    row.currency = currency

        for row in self.assign_transport:
            if not row.assigned_vehicle:
                continue

            vehicle_status = frappe.get_value("Vehicle", row.assigned_vehicle, "status")
            if vehicle_status == "In Trip":
                existing_vehicle_trip = frappe.db.get_value(
                    "Vehicle Trip",
                    {"reference_doctype": row.doctype, "reference_docname": row.name},
                )
                if not existing_vehicle_trip:
                    frappe.throw(_("Vehicle {0} is in trip").format(row.assigned_vehicle))

    def before_save(self):
        # Assignment status logic
        if not self.assign_transport:
            self.assignment_status = "Waiting Assignment"

        elif self.cargo_type == "Container":
            assigned = [r.container_number for r in self.assign_transport]
            for c in self.cargo:
                status = "Fully Assigned" if c.container_number in assigned else "Partially Assigned"
                self.assignment_status = status

        elif self.cargo_type == "Loose Cargo":
            total_assigned = sum(r.get("amount", 0) for r in self.assign_transport)
            status = "Fully Assigned" if self.amount <= total_assigned else "Partially Assigned"
            self.assignment_status = status

    def get_all_children(self, parenttype=None):
        if self.reference_docname:
            return self.assign_transport

        ret = []
        for df in self.meta.get("fields", {"fieldtype": "Table"}):
            if parenttype and df.options == parenttype:
                return self.get(df.fieldname)
            val = self.get(df.fieldname)
            if isinstance(val, list):
                ret.extend(val)
        return ret

    def update_children(self):
        if self.reference_docname:
            self.update_child_table("assign_transport")
        else:
            for df in self.meta.get_table_fields():
                self.update_child_table(df.fieldname, df)

    def load_from_db(self):
        """Load document (and children) from DB into this Document object."""
        if not getattr(self, "_metaclass", False) and self.meta.issingle:
            single = frappe.db.get_singles_dict(self.doctype) or frappe.new_doc(self.doctype).as_dict()
            single["name"] = self.doctype
            del single["__islocal"]
            super(Document, self).__init__(single)
            self.init_valid_columns()
            self._fix_numeric_types()
        else:
            record = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
            if not record:
                frappe.throw(_("{0} {1} not found").format(_(self.doctype), self.name), frappe.DoesNotExistError)
            super(Document, self).__init__(record)

        # Reload any child tables
        if self.name == "DocType" and self.doctype == "DocType":
            from frappe.model.meta import doctype_table_fields
            tables = doctype_table_fields
        else:
            tables = self.meta.get_table_fields()

        for df in tables:
            # handle imports case
            if record.get("reference_doctype") and record.get("reference_docname"):
                fieldname = df.fieldname
                if record.reference_doctype == "Import" and df.fieldname == "cargo":
                    fieldname = "cargo_information"
                elif record.reference_doctype == "Import" and df.fieldname == "assign_transport":
                    fieldname = "assign_transport"

                if df.fieldname == "assign_transport" and self.get("version") == 2:
                    children = frappe.db.get_values(df.options,
                        {"parent": self.name, "parenttype": self.doctype, "parentfield": "assign_transport"},
                        "*", as_dict=True, order_by="idx asc")
                else:
                    children = frappe.db.get_values(df.options,
                        {"parent": record.reference_docname, "parenttype": record.reference_doctype, "parentfield": fieldname},
                        "*", as_dict=True, order_by="idx asc")
            else:
                children = frappe.db.get_values(df.options,
                    {"parent": self.name, "parenttype": self.doctype, "parentfield": df.fieldname},
                    "*", as_dict=True, order_by="idx asc")

            self.set(df.fieldname, children or [])

        if hasattr(self, "__setup__"):
            self.__setup__()

    def create_sales_invoice(self):
        # 1) Gather transport rows
        rows = self.assign_transport or []
        items, item_row_per = [], []

        # 2) Build items and descriptions
        for row in rows:
            desc = ""
            if row.transporter_type == "In House" and row.assigned_vehicle:
                desc += f"<b>VEHICLE NUMBER: {row.assigned_vehicle}"
                if row.created_trip:
                    desc += f"<br>TRIP: {row.created_trip}"
            elif row.transporter_type == "Sub-Contractor" and row.vehicle_plate_number:
                desc += f"<b>VEHICLE NUMBER: {row.vehicle_plate_number}"
            if row.route:
                desc += f"<br>ROUTE: {row.route}"

            itm = {"item_code": row.item, "qty": 1, "description": desc}
            items.append(itm)
            item_row_per.append((row, itm))

        # 3) Instantiate the Sales Invoice
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "posting_date": nowdate(),
            "items": items
        })

        # 4) Dynamic dept_abbr lookup
        dept_abbr = getattr(self, "department_abbr", None) \
                   or (frappe.db.has_column("Customer", "department_abbr")
                       and frappe.db.get_value("Customer", self.customer, "department_abbr")) \
                   or (frappe.db.has_column("Company", "abbr")
                       and frappe.db.get_value("Company", self.company, "abbr"))

        if not dept_abbr:
            frappe.throw(_("Missing department abbreviation for naming series."))

        # 5) Override auto-naming
        invoice.naming_series = None
        invoice.name = make_autoname(f"ACC-SINV-{dept_abbr}-.YYYY.-")

        # 6) Apply your dimensions
        for row, itm in item_row_per:
            set_dimension(self, invoice, src_child=row, tr_child=itm)

        # 7) Finalize & insert
        frappe.flags.ignore_account_permission = True
        invoice.set_taxes()
        invoice.set_missing_values()
        invoice.insert(ignore_permissions=True)

        # 8) Link back to transport rows
        for row, _ in item_row_per:
            row.db_set("invoice", invoice.name)

        frappe.msgprint(_(f"Sales Invoice {invoice.name} created"), alert=True)
        return invoice


@frappe.whitelist(allow_guest=True)
def transport_order_scheduler():
    for row in frappe.db.sql(
        """SELECT name, eta, reference_file_number
           FROM `tabImport`
           WHERE (status <> 'Closed' OR status IS NULL)
             AND eta < timestampadd(day, -10, now())""",
        as_dict=1
    ):
        create_transport_order(
            reference_doctype="Import",
            reference_docname=row.name,
            file_number=row.reference_file_number,
        )


@frappe.whitelist(allow_guest=True)
def create_transport_order(**args):
    args = frappe._dict(args)
    existing = frappe.db.get_value("Transport Order", {"file_number": args.file_number})

    if not existing:
        req = frappe.new_doc("Transportion Order")
        req.update({
            "reference_doctype":  args.reference_doctype,
            "reference_docname":  args.reference_docname,
            "file_number":        args.file_number,
            "request_received":   args.request_received,
            "customer":           args.customer,
            "consignee":          args.consignee,
            "shipper":            args.shipper,
            "cargo_location_country": args.cargo_location_country,
            "cargo_location_city":    args.cargo_location_city,
            "cargo_destination_country": args.cargo_destination_country,
            "cargo_destination_city":    args.cargo_destination_city,
            "transport_type":     args.transport_type,
            "version":            2,
        })
        req.insert(ignore_permissions=True)
        return req.name

    return existing


@frappe.whitelist(allow_guest=True)
def assign_vehicle(**args):
    args = frappe._dict(args)
    existing = frappe.db.get_value("Transport Assignment", {"cargo": args.cargo_docname})

    if existing:
        doc = frappe.get_doc("Transport Assignment", existing)
        for field in [
            "assigned_vehicle","assigned_trailer","assigned_driver","cargo",
            "amount","expected_loading_date","container_number","units",
            "transporter_type","sub_contractor","vehicle_plate_number",
            "trailer_plate_number","driver_name","passport_number",
            "route","idx"
        ]:
            setattr(doc, field, args.get(field))
        doc.save()
    else:
        req = frappe.new_doc("Transport Assignment")
        req.update({
            "cargo":                   args.cargo_docname,
            "amount":                  args.amount,
            "expected_loading_date":   args.expected_loading_date,
            "container_number":        args.container_number,
            "units":                   args.units,
            "transporter_type":        args.transporter_type,
            "sub_contractor":          args.sub_contractor,
            "vehicle_plate_number":    args.vehicle_plate_number,
            "trailer_plate_number":    args.trailer_plate_number,
            "driver_name":             args.driver_name,
            "passport_number":         args.passport_number,
            "route":                   args.route,
            "parent":                  args.reference_docname,
            "parenttype":              args.reference_doctype,
            "parentfield":             "assign_transport",
            "assigned_vehicle":        args.assigned_vehicle,
            "assigned_trailer":        args.assigned_trailer,
            "assigned_driver":         args.assigned_driver,
            "idx":                     args.assigned_idx,
        })
        req.insert(ignore_permissions=True)

    return "success"
