// window.rs — Tables: shared chrome + native cell grid.
// SPDX-License-Identifier: GPL-3.0-or-later

use gtk4 as gtk;
use gtk::prelude::*;

const ROWS: usize = 100;
const COLS: usize = 26;

pub struct TablesWindow {
    window: gtk::ApplicationWindow,
    _grid: gtk::ListView,
    model: gtk::gio::ListStore,
}

impl TablesWindow {
    pub fn new(app: &gtk::Application) -> Self {
        let win = gtk::ApplicationWindow::builder().application(app).build();
        win.set_title(Some("Tables"));
        win.set_default_size(900, 600);

        // Shared chrome
        let header = suite_common::make_header_bar();
        let toolbar = suite_common::make_toolbar();
        let formula_bar = gtk::Entry::new();
        formula_bar.set_placeholder_text(Some("Formula…"));

        // ── Grid ──────────────────────────────────────────────
        let model = gtk::gio::ListStore::new(gtk::glib::Type::OBJECT);
        for _ in 0..ROWS {
            model.append(&gtk::glib::Object::new());
        }

        let factory = gtk::SignalListItemFactory::new();
        factory.connect_setup(move |_factory, item| {
            let row_box = gtk::Box::new(gtk::Orientation::Horizontal, 0);
            // Row header (col number)
            let header_cell = gtk::Label::new(None);
            header_cell.set_width_chars(4);
            header_cell.add_css_class("dim-label");
            row_box.append(&header_cell);
            // Data cells
            for _ in 0..COLS {
                let cell = gtk::Entry::new();
                cell.set_has_frame(false);
                cell.set_width_chars(10);
                cell.set_hexpand(true);
                // Tab to next cell
                let next = cell.clone();
                cell.connect_activate(move |e| {
                    if let Some(parent) = e.parent() {
                        if let Some(sibling) = parent.next_sibling() {
                            if let Ok(entry) = sibling.downcast::<gtk::Box>() {
                                if let Some(first) = entry.first_child() {
                                    first.grab_focus();
                                }
                            }
                        }
                    }
                });
                row_box.append(&cell);
            }
            if let Some(list_item) = item.downcast_ref::<gtk::ListItem>() {
                list_item.set_child(Some(&row_box));
            }
        });

        factory.connect_bind(move |_factory, item| {
            if let Some(list_item) = item.downcast_ref::<gtk::ListItem>() {
                let row = list_item.position() as usize;
                if let Some(child) = list_item.child() {
                    if let Ok(row_box) = child.downcast::<gtk::Box>() {
                        // Set row header
                        if let Some(h) = row_box.first_child() {
                            if let Ok(label) = h.downcast::<gtk::Label>() {
                                label.set_label(&format!("{}", row + 1));
                            }
                        }
                        // Set cell values (column headers in row 0)
                        let mut w = row_box.first_child();
                        // Skip row header
                        w = w.and_then(|c| c.next_sibling());
                        let mut col = 0;
                        while let Some(entry) = w {
                            if col < COLS {
                                if let Ok(e) = entry.downcast::<gtk::Entry>() {
                                    if row == 0 {
                                        let col_name = std::char::from_u32(b'A' as u32 + col as u32).unwrap_or('?');
                                        e.set_text(&col_name.to_string());
                                    } else {
                                        e.set_text("");
                                    }
                                }
                            }
                            w = entry.next_sibling();
                            col += 1;
                        }
                    }
                }
            }
        });

        let grid = gtk::ListView::new(
            Some(gtk::SingleSelection::new(Some(model.clone()))),
            Some(factory),
        );
        let scroll = gtk::ScrolledWindow::new();
        scroll.set_child(Some(&grid));
        scroll.set_vexpand(true);

        let main_box = gtk::Box::new(gtk::Orientation::Vertical, 2);
        main_box.append(&toolbar);
        main_box.append(&formula_bar);
        main_box.append(&scroll);

        let container = gtk::Box::new(gtk::Orientation::Vertical, 0);
        container.append(&header);
        container.append(&main_box);
        win.set_child(Some(win.set_child(Some(&container))container));

        Self { window: win, _grid: grid, model }
    }

    pub fn present(&self) {
        self.window.present();
    }
}
