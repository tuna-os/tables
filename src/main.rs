// main.rs — Tables spreadsheet, pure Rust + gtk4-rs.
// SPDX-License-Identifier: GPL-3.0-or-later

use gtk4 as gtk;
use gtk::prelude::*;
use adw::prelude::*;

mod window;
mod engine;

fn main() {
    let app = adw::Application::builder()
        .application_id("org.tunaos.tables")
        .build();

    app.connect_activate(|app| {
        let win = window::TablesWindow::new(app);
        win.present();
    });

    app.run();
}
