mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
mkfile_dir := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: all compile rbac \
	build build/static_jquery_min.js build/static_jquery.js build/static_jquery-ui.zip \
	static static_production static_production_sprintf \
	static_production_jquery static_production_jquery-ui static_production_jquery-notify static_production_readmore static_production_jquery-appendGrid \


all: rbac

compile:
	./util/deploy/compile.py

rbac:
	PYTHONPATH=${mkfile_dir} ./util/deploy/rbac.py

clean:
	find handlers -name *.pyc -delete
	find modules -name *.pyc -delete
	find util -name *.pyc -delete
	find config -name *.pyc -delete
	find handlers -name __pycache__ -delete
	find modules -name __pycache__ -delete
	find util -name __pycache__ -delete
	find config -name __pycache__ -delete

# static directory

static:
	mkdir -p run/static
	mkdir -p run/static/image
	mkdir -p run/static/superfish/css
	mkdir -p run/static/superfish/js

run/static/% : resource/%
	cp $< $@

static_production: static \
	run/static/root.css run/static/transaction.css run/static/transaction_list.js run/static/transaction_checker.js \
	run/static/mailbox.css \
	run/static/agent_edit.js \
	run/static/image/valid.png run/static/image/invalid.png run/static/image/not_checked.png \
	static_production_sprintf \
	static_production_jquery static_production_jquery-ui static_production_jquery-notify static_production_readmore static_production_jquery-appendGrid \
	$(patsubst %,run/static/superfish/css/%.css,megafish superfish superfish-navbar superfish-vertical) \
	$(patsubst %,run/static/superfish/js/%.js,superfish hoverIntent) \


build:
	mkdir -p build

static_production_sprintf: build
	curl -o run/static/sprintf.js "https://raw.githubusercontent.com/alexei/sprintf.js/1.1.2/dist/sprintf.min.js"

build/static_jquery.js: build
	curl -o $@ "https://code.jquery.com/jquery-3.6.0.js"

build/static_jquery_min.js: build
	curl -o $@ "https://code.jquery.com/jquery-3.6.0.min.js"

build/static_jquery-ui.zip: build
	curl -o $@ "https://jqueryui.com/resources/download/jquery-ui-1.13.1.zip"

build/static_jquery-notify.zip: build
	curl -L -o $@ "https://github.com/vincentkeizer/notify/zipball/0.4.4"

build/static_readmore.zip: build
	curl -L -o $@ "https://github.com/jedfoster/Readmore.js/archive/refs/tags/2.2.1.zip"

build/static_jquery-appendGrid.css: build
	curl -L -o $@ "https://raw.githubusercontent.com/hkalbertl/jquery.appendGrid/1.4.2/jquery.appendGrid-1.4.2.min.css"

build/static_jquery-appendGrid.js: build
	curl -L -o $@ "https://raw.githubusercontent.com/hkalbertl/jquery.appendGrid/1.4.2/jquery.appendGrid-1.4.2.min.js"

static_production_jquery: static build/static_jquery_min.js
	cp "build/static_jquery_min.js" "run/static/jquery.js"

static_production_jquery-ui: static build/static_jquery-ui.zip
	mkdir -p run/static/jquery-ui
	unzip -p "build/static_jquery-ui.zip" jquery-ui-1.13.1/jquery-ui.min.css > run/static/jquery-ui/main.css
	unzip -p "build/static_jquery-ui.zip" jquery-ui-1.13.1/jquery-ui.structure.min.css > run/static/jquery-ui/structure.css
	unzip -p "build/static_jquery-ui.zip" jquery-ui-1.13.1/jquery-ui.theme.min.css > run/static/jquery-ui/theme.css
	unzip -p "build/static_jquery-ui.zip" jquery-ui-1.13.1/jquery-ui.min.js > run/static/jquery-ui/main.js
	mkdir -p run/static/jquery-ui/images
	unzip -o -j "build/static_jquery-ui.zip" "jquery-ui-1.13.1/images/*" -d run/static/jquery-ui/images/

static_production_jquery-notify: static build/static_jquery-notify.zip
	mkdir -p run/static/jquery-notify
	unzip -p "build/static_jquery-notify.zip" "vincentkeizer-notify-97ca89e/notify.min.css" > run/static/jquery-notify/main.css
	unzip -p "build/static_jquery-notify.zip" "vincentkeizer-notify-97ca89e/jquery-notify.min.js" > run/static/jquery-notify/main.js

static_production_readmore: static build/static_readmore.zip
	mkdir -p run/static/readmore
	unzip -p build/static_readmore.zip "Readmore.js-2.2.1/readmore.min.js" > run/static/readmore/main.js

static_production_jquery-appendGrid: static build/static_jquery-appendGrid.css build/static_jquery-appendGrid.js
	mkdir -p run/static/jquery-appendGrid
	cp build/static_jquery-appendGrid.css run/static/jquery-appendGrid/main.css
	cp build/static_jquery-appendGrid.js run/static/jquery-appendGrid/main.js

run/static/superfish/css/megafish.css:
	curl -L -o $@ "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/megafish.css"

run/static/superfish/css/superfish.css:
	curl -L -o $@ "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/superfish.css"

run/static/superfish/css/superfish-navbar.css:
	curl -L -o $@ "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/superfish-navbar.css"

run/static/superfish/css/superfish-vertical.css:
	curl -L -o $@ "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/superfish-vertical.css"

run/static/superfish/js/superfish.js:
	curl -L -o $@ "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/js/superfish.min.js"

run/static/superfish/js/hoverIntent.js:
	curl -L -o $@ "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/js/hoverIntent.js"

