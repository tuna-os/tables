// window.rs — Tables main window: native GTK4 cell grid.
// SPDX-License-Identifier: GPL-3.0-or-later

use gtk4 as gtk;
use gtk::prelude::*;
use gtk::{gio, glib};
use libadwaita::prelude::AdwApplicationWindowExt;  // for set_content

const ROWS: usize = 100;
const COLS: usize = 26;

pub struct TablesWindow {
    window: adw::ApplicationWindow,
    cells: std::cell::RefCell<Vec<Vec<String>>>,
}

impl TablesWindow {
    pub fn new(app: &adw::Application) -> Self {
        let window = adw::ApplicationWindow::new(app);
        window.set_title(Some("Tables"));
        window.set_default_size(800, 600);

        let mut cells: Vec<Vec<String>> = Vec::with_capacity(ROWS);
        for r in 0..ROWS {
            let mut row = Vec::with_capacity(COLS);
            for c in 0..COLS {
                let val = if r == 0 { 
                    String::from_utf8(vec![b'A' + c as u8]).unwrap()
                } else {
                    format!("{},{}", r, c)
                };
                row.push(val);
            }
            cells.push(row);
        }
        let cells = std::cell::RefCell::new(cells);

        let header = adw::HeaderBar::new();
        let open_btn = gtk::Button::with_label("Open");
        header.pack_start(&open_btn);
        let save_btn = gtk::Button::with_label("Save");
        header.pack_start(&save_btn);

        let toolbar = gtk::Box::new(gtk::Orientation::Horizontal, 4);
        toolbar.set_halign(gtk::Align::Center);
        toolbar.add_css_class("toolbar");
        toolbar.append(&gtk::ToggleButton::with_label("B"));
        toolbar.append(&gtk::ToggleButton::with_label("I"));
        toolbar.append(&gtk::ToggleButton::with_label("U"));

        let formula_bar = gtk::Entry::new();
        formula_bar.set_placeholder_text(Some("Formula…"));

        // Row list model
        let list_model = gio::ListStore::new::<glib::Object>();
        for _ in 0..ROWS {
            list_model.append(&glib::Object::new::<glib::Object>());
        }

        let cells_clone = cells.clone();
        let factory = gtk::SignalListItemFactory::new();
        factory.connect_setup(move |_factory, item| {
            let row_box = gtk::Box::new(gtk::Orientation::Horizontal, 0);
            for _ in 0..COLS {
                let cell = gtk::Entry::new();
                cell.set_has_frame(false);
                cell.set_width_chars(8);
                cell.set_hexpand(true);
                row_box.append(&cell);
            }
            if let Some(list_item) = item.downcast_ref::<gtk::ListItem>() {
                list_item.set_child(Some(&row_box));
            }
        });
        factory.connect_bind(move |_factory, item| {
            if let Some(list_item) = item.downcast_ref::<gtk::ListItem>() {
                let r = list_item.position() as usize;
                let data = cells_clone.borrow();
                if let Some(child) = list_item.child() {
                    if let Ok(row_box) = child.downcast::<gtk::Box>() {
                        let mut w = row_box.first_child();
                        let mut c = 0;
                        while let Some(entry) = w {
                            if c < COLS {
                                if let Ok(e) = entry.downcast::<gtk::Entry>() {
                                    e.set_text(&data[r][c]);
                                }
                            }
                            w = entry.next_sibling();
                            c += 1;
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

        let main_box = gtk::Box::new(gtk::Orientation::Vertical, 2);
        main_box.append(&toolbar);
        main_box.append(&formula_bar);
        main_box.append(&scroll);

        // Use Box instead of ToolbarView (gtk4-rs adw API differs)
        let container = gtk::Box::new(gtk::Orientation::Vertical, 0);
        container.append(&header);
        container.append(&main_box);
        window.set_content(Some(&container));

        Self { window, cells }
    }

    pub fn present(&self) {
        self.window.present();
    }
}
