// window.rs — Tables main window: native GTK4 cell grid.
// SPDX-License-Identifier: GPL-3.0-or-later

use gtk4 as gtk;
use gtk::prelude::*;
use adw::prelude::*;

use crate::engine;

pub struct TablesWindow {
    window: adw::ApplicationWindow,
    spreadsheet: std::cell::RefCell<engine::Spreadsheet>,
}

impl TablesWindow {
    pub fn new(app: &adw::Application) -> Self {
        let window = adw::ApplicationWindow::new(app);
        window.set_title(Some("Tables"));
        window.set_default_size(800, 600);

        // ── Data model ───────────────────────────────────────
        let rows = 100;
        let cols = 26;  // A-Z
        let mut sheet = engine::Spreadsheet::new(rows, cols);
        // Header row
        for c in 0..cols {
            let col_name = if c < 26 {
                String::from_utf8(vec![b'A' + c as u8]).unwrap()
            } else { format!("C{}", c) };
            sheet.set(0, c, &col_name);
        }
        // Sample data
        sheet.set(1, 0, "10");
        sheet.set(1, 1, "20");
        sheet.set(1, 2, "30");
        sheet.set_formula(2, 0, "=SUM(A2:A2)");  // IronCalc uses 1-based
        sheet.set_formula(2, 1, "=A2+B2+C2");
        sheet.recalc();

        let sheet_ref = std::cell::RefCell::new(sheet);

        // ── Header bar ──────────────────────────────────────
        let header = adw::HeaderBar::new();
        let open_btn = gtk::Button::with_label("Open");
        header.pack_start(&open_btn);
        let save_btn = gtk::Button::with_label("Save");
        header.pack_start(&save_btn);

        // ── Toolbar ─────────────────────────────────────────
        let toolbar = gtk::Box::new(gtk::Orientation::Horizontal, 4);
        toolbar.set_halign(gtk::Align::Center);
        toolbar.add_css_class("toolbar");
        let bold_btn = gtk::ToggleButton::with_label("B");
        let italic_btn = gtk::ToggleButton::with_label("I");
        let underline_btn = gtk::ToggleButton::with_label("U");
        toolbar.append(&bold_btn);
        toolbar.append(&italic_btn);
        toolbar.append(&underline_btn);

        // ── Row factory (one entry per row) ─────────────────
        let list_model = gio::ListStore::new(glib::Type::OBJECT);
        for _ in 0..sheet_ref.borrow().rows {
            list_model.append(&glib::Object::new());
        }

        let factory = gtk::SignalListItemFactory::new();
        let sheet_clone = sheet_ref.clone();
        factory.connect_setup(|_factory, item| {
            let row_box = gtk::Box::new(gtk::Orientation::Horizontal, 0);
            // Create entry for each column
            for _ in 0..sheet_clone.borrow().cols {
                let cell = gtk::Entry::new();
                cell.set_has_frame(false);
                cell.set_width_chars(10);
                cell.set_hexpand(true);
                row_box.append(&cell);
            }
            if let Some(list_item) = item.downcast_ref::<gtk::ListItem>() {
                list_item.set_child(Some(&row_box));
            }
        });
        factory.connect_bind(move |_factory, item| {
            if let Some(list_item) = item.downcast_ref::<gtk::ListItem>() {
                let row = list_item.position() as usize;
                let sheet = sheet_ref.borrow();
                if let Some(child) = list_item.child() {
                    if let Ok(row_box) = child.downcast::<gtk::Box>() {
                        let mut widget = row_box.first_child();
                        let mut col = 0;
                        while let Some(entry) = widget {
                            if col < sheet.cols {
                                if let Ok(e) = entry.downcast::<gtk::Entry>() {
                                    e.set_text(sheet.get(row, col));
                                }
                            }
                            widget = entry.next_sibling();
                            col += 1;
                        }
                    }
                }
            }
        });

        let list_view = gtk::ListView::new(
            Some(gtk::SingleSelection::new(Some(list_model))),
            Some(factory),
        );

        let scroll = gtk::ScrolledWindow::new();
        scroll.set_child(Some(&list_view));
        scroll.set_vexpand(true);

        // ── Formula bar ─────────────────────────────────────
        let formula_bar = gtk::Entry::new();
        formula_bar.set_placeholder_text(Some("Formula…"));

        // ── Layout ──────────────────────────────────────────
        let main_box = gtk::Box::new(gtk::Orientation::Vertical, 2);
        main_box.append(&toolbar);
        main_box.append(&formula_bar);
        main_box.append(&scroll);

        let toolbar_view = adw::ToolbarView::new();
        toolbar_view.add_top_bar(&header);
        toolbar_view.set_content(Some(&main_box));
        window.set_content(Some(&toolbar_view));

        Self { window, spreadsheet: sheet_ref }
    }

    pub fn present(&self) {
        self.window.present();
    }
}
