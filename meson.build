project('tables',
  version: '0.1.10',
  meson_version: '>= 1.0.0',
  default_options: [ 'warning_level=2', 'werror=false' ],
)

gnome = import('gnome')

subdir('data')
subdir('src')

gnome.post_install(
  update_desktop_database: true,
)
