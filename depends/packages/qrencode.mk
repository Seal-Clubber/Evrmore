package=qrencode
$(package)_version=3.4.4
#$(package)_download_path=https://fukuchi.org/works/qrencode/
$(package)_download_path=https://github.com/fukuchi/libqrencode/archive/refs/tags/
#$(package)_file_name=$(package)-$($(package)_version).tar.bz2
$(package)_file_name=v$($(package)_version).tar.gz
#$(package)_sha256_hash=efe5188b1ddbcbf98763b819b146be6a90481aac30cfc8d858ab78a19cde1fa5
$(package)_sha256_hash=ab7cdf84e3707573a39e116ebd33faa513b306201941df3f5e691568368d87bf

define $(package)_set_vars
$(package)_config_opts=--disable-shared -without-tools --disable-sdltest
$(package)_config_opts_linux=--with-pic
endef

define $(package)_config_cmds
  $($(package)_autoconf)
endef

define $(package)_build_cmds
  $(MAKE)
endef

define $(package)_stage_cmds
  $(MAKE) DESTDIR=$($(package)_staging_dir) install
endef
