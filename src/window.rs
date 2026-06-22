// window.rs — Tables main window: toolbar + grid.
// SPDX-License-Identifier: GPL-3.0-or-later

use gtk4 as gtk;
use gtk::prelude::*;
use adw::prelude::*;

use crate::engine;

pub struct TablesWindow {
    window: adw::ApplicationWindow,
    grid: gtk::TextView,
}

impl TablesWindow {
    pub fn new(app: &adw::Application) -> Self {
        let window = adw::ApplicationWindow::new(app);
        window.set_title(Some("Tables"));
        window.set_default_size(800, 600);

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

        // ── Grid (text area for now; replace with native grid) ──
        let grid = gtk::TextView::new();
        grid.set_editable(true);
        grid.set_monospace(true);
        let scroll = gtk::ScrolledWindow::new();
        scroll.set_child(Some(&grid));
        scroll.set_vexpand(true);

        // ── Layout ──────────────────────────────────────────
        let toolbar_view = adw::ToolbarView::new();
        toolbar_view.add_top_bar(&header);
        toolbar_view.add_top_bar(&toolbar);
        toolbar_view.set_content(Some(&scroll));
        window.set_content(Some(&toolbar_view));

        let s = Self { window, grid };
        s.load_test_data();
        s
    }

    fn load_test_data(&self) {
        let buf = self.grid.buffer();
        let mut text = String::new();
        for row in 0..20 {
            for col in 0..5 {
                if row == 0 && col == 0 {
                    text.push_str("Rust Tables 🦀");
                } else {
                    text.push_str(&format!("{},{}", row, col));
                }
                if col < 4 { text.push('\t'); }
            }
            text.push('\n');
        }
        buf.set_text(&text);
    }

    pub fn present(&self) {
        self.window.present();
    }
}
