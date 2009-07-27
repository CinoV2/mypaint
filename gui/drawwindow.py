# -*- coding: utf-8 -*-
#
# This file is part of MyPaint.
# Copyright (C) 2007-2008 by Martin Renold <martinxyz@gmx.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""
This is the main drawing window, containing menu actions.
Painting is done in tileddrawwidget.py.
"""

MYPAINT_VERSION="0.7.1+git"

import os, re, math
from gettext import gettext as _
from glob import glob

import gtk
from gtk import gdk, keysyms

import tileddrawwidget, colorselectionwindow, historypopup, \
       stategroup, keyboard, colorpicker
from lib import document, helpers, backgroundsurface, command

class Window(gtk.Window):
    def __init__(self, app):
        gtk.Window.__init__(self)
        self.app = app

        self.connect('delete-event', self.quit_cb)
        self.connect('key-press-event', self.key_press_event_cb_before)
        self.connect('key-release-event', self.key_release_event_cb_before)
        self.connect_after('key-press-event', self.key_press_event_cb_after)
        self.connect_after('key-release-event', self.key_release_event_cb_after)
        self.connect("button-press-event", self.button_press_cb)
        self.connect("button-release-event", self.button_release_cb)
        self.connect("scroll-event", self.scroll_cb)
        self.set_default_size(600, 400)
        vbox = gtk.VBox()
        self.add(vbox)

        self.doc = document.Document()
        self.doc.set_brush(self.app.brush)

        self.create_ui()
        self.menubar = self.ui.get_widget('/Menubar')
        vbox.pack_start(self.menubar, expand=False)

        self.tdw = tileddrawwidget.TiledDrawWidget(self.doc)
        vbox.pack_start(self.tdw)

        # FIXME: hack, to be removed
        filename = os.path.join(self.app.datapath, 'backgrounds', '03_check1.png')
        pixbuf = gdk.pixbuf_new_from_file(filename)
        self.tdw.neutral_background_pixbuf = backgroundsurface.Background(pixbuf)

        self.zoomlevel_values = [1.0/8, 2.0/11, 0.25, 1.0/3, 0.50, 2.0/3, 1.0, 1.5, 2.0, 3.0, 4.0, 5.5, 8.0]
        self.zoomlevel = self.zoomlevel_values.index(1.0)
        self.tdw.zoom_min = min(self.zoomlevel_values)
        self.tdw.zoom_max = max(self.zoomlevel_values)
        self.fullscreen = False

        self.app.brush.settings_observers.append(self.brush_modified_cb)
        self.tdw.device_observers.append(self.device_changed_cb)
            
        fn = os.path.join(self.app.confpath, 'save_history.conf')
        if os.path.exists(fn):
            self.save_history = [line.strip() for line in open(fn)]
        else:
            self.save_history = []

        self.init_save_dialog()

        #filename is a property so that all changes will update the title
        self.filename = None

        self.eraser_mode_radius_change = 3*(0.3) # can go back to exact original with brush_smaller_cb()
        self.eraser_mode_original_radius = None
        
        
    def get_filename(self):
        return self._filename 
    def set_filename(self,value):
        self._filename = value
        if self.filename: 
            self.set_title("MyPaint - %s" % os.path.basename(self.filename))
        else:
            self.set_title("MyPaint")
    filename = property(get_filename, set_filename)

    def create_ui(self):
        ag = self.action_group = gtk.ActionGroup('WindowActions')
        # FIXME: this xml menu only creates unneeded information duplication, I think.
		# FIXME: better just use glade...
        ui_string = """<ui>
          <menubar name='Menubar'>
            <menu action='FileMenu'>
              <menuitem action='New'/>
              <menuitem action='Open'/>
              <menuitem action='OpenRecent'/>
              <separator/>
              <menuitem action='Save'/>
              <menuitem action='SaveAs'/>
              <menuitem action='SaveScrap'/>
              <separator/>
              <menuitem action='Quit'/>
            </menu>
            <menu action='EditMenu'>
              <menuitem action='Undo'/>
              <menuitem action='Redo'/>
              <separator/>
              <menuitem action='SettingsWindow'/>
            </menu>
            <menu action='ViewMenu'>
              <menuitem action='Fullscreen'/>
              <separator/>
              <menuitem action='ResetView'/>
              <menuitem action='ZoomIn'/>
              <menuitem action='ZoomOut'/>
              <menuitem action='RotateLeft'/>
              <menuitem action='RotateRight'/>
              <menuitem action='Flip'/>
              <separator/>
              <menuitem action='SoloLayer'/>
              <menuitem action='ToggleAbove'/>
              <separator/>
              <menuitem action='ViewHelp'/>
            </menu>
            <menu action='BrushMenu'>
              <menuitem action='BrushSelectionWindow'/>
              <menu action='ContextMenu'>
                <menuitem action='ContextStore'/>
                <separator/>
                <menuitem action='Context00'/>
                <menuitem action='Context00s'/>
                <menuitem action='Context01'/>
                <menuitem action='Context01s'/>
                <menuitem action='Context02'/>
                <menuitem action='Context02s'/>
                <menuitem action='Context03'/>
                <menuitem action='Context03s'/>
                <menuitem action='Context04'/>
                <menuitem action='Context04s'/>
                <menuitem action='Context05'/>
                <menuitem action='Context05s'/>
                <menuitem action='Context06'/>
                <menuitem action='Context06s'/>
                <menuitem action='Context07'/>
                <menuitem action='Context07s'/>
                <menuitem action='Context08'/>
                <menuitem action='Context08s'/>
                <menuitem action='Context09'/>
                <menuitem action='Context09s'/>
                <separator/>
                <menuitem action='ContextHelp'/>
              </menu>
              <separator/>
              <menuitem action='BrushSettingsWindow'/>
              <separator/>
              <menuitem action='Bigger'/>
              <menuitem action='Smaller'/>
              <menuitem action='MoreOpaque'/>
              <menuitem action='LessOpaque'/>
              <separator/>
              <menuitem action='Eraser'/>
              <separator/>
              <menuitem action='PickContext'/>
            </menu>
            <menu action='ColorMenu'>
              <menuitem action='ColorSelectionWindow'/>
              <menuitem action='ColorRingPopup'/>
              <menuitem action='ColorChangerPopup'/>
              <menuitem action='ColorPickerPopup'/>
              <menuitem action='ColorHistoryPopup'/>
              <menuitem action='ColorSamplerWindow'/>
              <separator/>
              <menuitem action='Brighter'/>
              <menuitem action='Darker'/>
            </menu>
            <menu action='LayerMenu'>
              <menuitem action='BackgroundWindow'/>
              <separator/>
              <menuitem action='ClearLayer'/>
              <menuitem action='RemoveLayer'/>
              <menuitem action='MergeLayer'/>
              <separator/>
              <menuitem action='NewLayerFG'/>
              <menuitem action='NewLayerBG'/>
              <separator/>
              <menuitem action='PickLayer'/>
              <menuitem action='LayerFG'/>
              <menuitem action='LayerBG'/>
              <separator/>
              <menuitem action='CopyLayer'/>
              <menuitem action='PasteLayer'/>
              <separator/>
              <menuitem action='IncreaseLayerOpacity'/>
              <menuitem action='DecreaseLayerOpacity'/>
            </menu>
            <menu action='DebugMenu'>
              <menuitem action='PrintInputs'/>
              <menuitem action='VisualizeRendering'/>
              <menuitem action='NoDoubleBuffereing'/>
            </menu>
            <menu action='HelpMenu'>
              <menuitem action='Docu'/>
              <menuitem action='ShortcutHelp'/>
              <separator/>
              <menuitem action='About'/>
            </menu>
          </menubar>
        </ui>"""
        actions = [
			# name, stock id, label, accelerator, tooltip, callback
            ('FileMenu',     None, _('File')),
            ('New',          None, _('New'), '<control>N', None, self.new_cb),
            ('Open',         None, _('Open...'), '<control>O', None, self.open_cb),
            ('OpenRecent',   None, _('Open Recent'), 'F3', None, self.open_recent_cb),
            ('Save',         None, _('Save'), '<control>S', None, self.save_cb),
            ('SaveAs',       None, _('Save As...'), '<control><shift>S', None, self.save_as_cb),
            ('SaveScrap',    None, _('Save Next Scrap'), 'F2', None, self.save_scrap_cb),
            ('Quit',         None, _('Quit'), '<control>q', None, self.quit_cb),


            ('EditMenu',           None, _('Edit')),
            ('Undo',               None, _('Undo'), 'Z', None, self.undo_cb),
            ('Redo',               None, _('Redo'), 'Y', None, self.redo_cb),

            ('BrushMenu',    None, _('Brush')),
            ('Brighter',     None, _('Brighter'), None, None, self.brighter_cb),
            ('Smaller',      None, _('Smaller'), 'd', None, self.brush_smaller_cb),
            ('MoreOpaque',   None, _('More Opaque'), 's', None, self.more_opaque_cb),
            ('LessOpaque',   None, _('Less Opaque'), 'a', None, self.less_opaque_cb),
            ('Eraser',       None, _('Toggle Eraser Mode'), 'e', None, self.eraser_cb),
            ('PickContext',  None, _('Pick Context (layer, brush and color)'), 'w', None, self.pick_context_cb),

            ('ColorMenu',    None, _('Color')),
            ('Darker',       None, _('Darker'), None, None, self.darker_cb),
            ('Bigger',       None, _('Bigger'), 'f', None, self.brush_bigger_cb),
            ('ColorPickerPopup',    None, _('Pick Color'), 'r', None, self.popup_cb),
            ('ColorHistoryPopup',  None, _('Color History'), 'x', None, self.popup_cb),
            ('ColorChangerPopup', None, _('Color Changer'), 'v', None, self.popup_cb),
            ('ColorRingPopup',  None, _('Color Ring'), None, None, self.popup_cb),

            ('ContextMenu',  None, _('Brushkeys')),
            #each of the context actions are generated and added below
            ('ContextStore', None, _('Save to Most Recently Restored'), 'q', None, self.context_cb),
            ('ContextHelp',  None, _('Help!'), None, None, self.show_infodialog_cb),

            ('LayerMenu',    None, _('Layers')),

            ('BackgroundWindow', None, _('Background...'), None, None, self.toggleWindow_cb),
            ('ClearLayer',   None, _('Clear'), 'Delete', None, self.clear_layer_cb),
            ('CopyLayer',          None, _('Copy to Clipboard'), '<control>C', None, self.copy_cb),
            ('PasteLayer',         None, _('Paste Clipboard (Replace Layer)'), '<control>V', None, self.paste_cb),
            ('PickLayer',    None, _('Select Layer at Cursor'), 'h', None, self.pick_layer_cb),
            ('LayerFG',      None, _('Next (above current)'),  'Page_Up', None, self.layer_fg_cb),
            ('LayerBG',      None, _('Next (below current)'), 'Page_Down', None, self.layer_bg_cb),
            ('NewLayerFG',   None, _('New (above current)'), '<control>Page_Up', None, self.new_layer_cb),
            ('NewLayerBG',   None, _('New (below current)'), '<control>Page_Down', None, self.new_layer_cb),
            ('MergeLayer',   None, _('Merge Down'), '<control>Delete', None, self.merge_layer_cb),
            ('RemoveLayer',  None, _('Remove'), '<shift>Delete', None, self.remove_layer_cb),
            ('IncreaseLayerOpacity', None, _('Increase Layer Opacity'),  'p', None, self.layer_increase_opacity),
            ('DecreaseLayerOpacity', None, _('Decrease Layer Opacity'),  'o', None, self.layer_decrease_opacity),

            ('BrushSelectionWindow',  None, _('Brush List...'), 'b', None, self.toggleWindow_cb),
            ('BrushSettingsWindow',   None, _('Brush Settings...'), '<control>b', None, self.toggleWindow_cb),
            ('ColorSelectionWindow',  None, _('Color Triangle...'), 'g', None, self.toggleWindow_cb),
            ('ColorSamplerWindow',  None, _('Color Sampler...'), 't', None, self.toggleWindow_cb),
            ('SettingsWindow',        None, _('Settings...'), None, None, self.toggleWindow_cb),

            ('HelpMenu',     None, _('Help')),
            ('Docu', None, _('Where is the Documentation?'), None, None, self.show_infodialog_cb),
            ('ShortcutHelp',  None, _('Change the Keyboard Shortcuts?'), None, None, self.show_infodialog_cb),
            ('About', None, _('About MyPaint'), None, None, self.show_infodialog_cb),

            ('DebugMenu',    None, _('Debug')),


            ('ShortcutsMenu', None, _('Shortcuts')),

            ('ViewMenu', None, _('View')),
            ('Fullscreen',   None, _('Fullscreen'), 'F11', None, self.fullscreen_cb),
            ('ResetView',   None, _('Reset (Zoom, Rotation, Mirror)'), None, None, self.reset_view_cb),
            ('ZoomIn',       None, _('Zoom In (at cursor)'), 'period', None, self.zoom_cb),
            ('ZoomOut',      None, _('Zoom Out'), 'comma', None, self.zoom_cb),
            ('RotateLeft',   None, _('Rotate Counterclockwise'), None, None, self.rotate_cb),
            ('RotateRight',  None, _('Rotate Clockwise'), None, None, self.rotate_cb),
            ('SoloLayer',    None, _('Layer Solo'), 'Home', None, self.solo_layer_cb),
            ('ToggleAbove',  None, _('Hide Layers Above Current'), 'End', None, self.toggle_layers_above_cb), # TODO: make toggle action
            ('ViewHelp',     None, _('Help'), None, None, self.show_infodialog_cb),
            ]
        ag.add_actions(actions)
        context_actions = []
        for x in range(10):
            r = ('Context0%d' % x,    None, _('Restore Brush %d') % x, 
                    '%d' % x, None, self.context_cb)
            s = ('Context0%ds' % x,   None, _('Save to Brush %d') % x, 
                    '<control>%d' % x, None, self.context_cb)
            context_actions.append(s)
            context_actions.append(r)
        ag.add_actions(context_actions)
        toggle_actions = [
            # name, stock id, label, accelerator, tooltip, callback, default toggle status
            ('PrintInputs', None, _('Print Brush Input Values to stdout'), None, None, self.print_inputs_cb),
            ('VisualizeRendering', None, _('Visualize Rendering'), None, None, self.visualize_rendering_cb),
            ('NoDoubleBuffereing', None, _('Disable GTK Double Buffering'), None, None, self.no_double_buffering_cb),
            ('Flip', None, _('Mirror Image'), 'i', None, self.flip_cb),
            ]
        ag.add_toggle_actions(toggle_actions)
        self.ui = gtk.UIManager()
        self.ui.insert_action_group(ag, 0)
        self.ui.add_ui_from_string(ui_string)
        #self.app.accel_group = self.ui.get_accel_group()

        self.app.kbm = kbm = keyboard.KeyboardManager()
        kbm.add_window(self)

        for action in ag.list_actions():
            self.app.kbm.takeover_action(action)

        kbm.add_extra_key('<control>z', 'Undo')
        kbm.add_extra_key('<control>y', 'Redo')
        kbm.add_extra_key('KP_Add', 'ZoomIn')
        kbm.add_extra_key('KP_Subtract', 'ZoomOut')
        kbm.add_extra_key('plus', 'ZoomIn')
        kbm.add_extra_key('minus', 'ZoomOut')

        kbm.add_extra_key('Left', lambda(action): self.move('MoveLeft'))
        kbm.add_extra_key('Right', lambda(action): self.move('MoveRight'))
        kbm.add_extra_key('Down', lambda(action): self.move('MoveDown'))
        kbm.add_extra_key('Up', lambda(action): self.move('MoveUp'))

        kbm.add_extra_key('<control>Left', 'RotateLeft')
        kbm.add_extra_key('<control>Right', 'RotateRight')

        sg = stategroup.StateGroup()
        self.layerblink_state = sg.create_state(self.layerblink_state_enter, self.layerblink_state_leave)

        # separate stategroup...
        sg2 = stategroup.StateGroup()
        self.layersolo_state = sg2.create_state(self.layersolo_state_enter, self.layersolo_state_leave)
        self.layersolo_state.autoleave_timeout = None

        p2s = sg.create_popup_state
        changer = p2s(colorselectionwindow.ColorChangerPopup(self.app))
        ring = p2s(colorselectionwindow.ColorRingPopup(self.app))
        hist = p2s(historypopup.HistoryPopup(self.app, self.doc))
        pick = self.colorpick_state = p2s(colorpicker.ColorPicker(self.app, self.doc))

        self.popup_states = {
            'ColorChangerPopup': changer,
            'ColorRingPopup': ring,
            'ColorHistoryPopup': hist,
            'ColorPickerPopup': pick,
            }
        changer.next_state = ring
        ring.next_state = changer
        changer.autoleave_timeout = None
        ring.autoleave_timeout = None

        pick.max_key_hit_duration = 0.0
        pick.autoleave_timeout = None

        hist.autoleave_timeout = 0.600
        self.history_popup_state = hist

    def with_wait_cursor(func):
        """python decorator that adds a wait cursor around a function"""
        def wrapper(self, *args, **kwargs):
            self.window.set_cursor(gdk.Cursor(gdk.WATCH))
            self.tdw.window.set_cursor(None)
            # make sure it is actually changed before we return
            while gtk.events_pending():
                gtk.main_iteration(False)
            try:
                func(self, *args, **kwargs)
            finally:
                self.window.set_cursor(None)
                self.tdw.update_cursor()
        return wrapper

    def toggleWindow_cb(self, action):
        s = action.get_name()
        s = s[0].lower() + s[1:]
        w = getattr(self.app, s)
        if w.window and w.window.is_visible():
            w.hide()
        else:
            w.show_all() # might be for the first time
            w.present()

    def print_inputs_cb(self, action):
        self.doc.brush.print_inputs = action.get_active()

    def visualize_rendering_cb(self, action):
        self.tdw.visualize_rendering = action.get_active()
    def no_double_buffering_cb(self, action):
        self.tdw.set_double_buffered(not action.get_active())
        
    def undo_cb(self, action):
        cmd = self.doc.undo()
        if isinstance(cmd, command.MergeLayer):
            # show otherwise invisible change (hack...)
            self.layerblink_state.activate()

    def redo_cb(self, action):
        cmd = self.doc.redo()
        if isinstance(cmd, command.MergeLayer):
            # show otherwise invisible change (hack...)
            self.layerblink_state.activate()

    def copy_cb(self, action):
        # use the full document bbox, so we can past layers back to the correct position
        bbox = self.doc.get_bbox()
        pixbuf = self.doc.layer.surface.render_as_pixbuf(*bbox)
        cb = gtk.Clipboard()
        cb.set_image(pixbuf)

    def paste_cb(self, action):
        cb = gtk.Clipboard()
        def callback(clipboard, pixbuf, trash):
            if not pixbuf:
                print 'The clipboard doeas not contain any image to paste!'
                return
            # paste to the upper left of our doc bbox (see above)
            x, y, w, h = self.doc.get_bbox()
            self.doc.load_layer_from_pixbuf(pixbuf, x, y)
        cb.request_image(callback)

    def brush_modified_cb(self):
        # called at every brush setting modification, should return fast
        self.doc.set_brush(self.app.brush)

    def key_press_event_cb_before(self, win, event):
        key = event.keyval 
        ctrl = event.state & gdk.CONTROL_MASK
        #ANY_MODIFIER = gdk.SHIFT_MASK | gdk.MOD1_MASK | gdk.CONTROL_MASK
        #if event.state & ANY_MODIFIER:
        #    # allow user shortcuts with modifiers
        #    return False
        if key == keysyms.space:
            if ctrl:
                self.tdw.start_drag(self.dragfunc_rotate)
            else:
                self.tdw.start_drag(self.dragfunc_translate)
        else: return False
        return True
    def key_release_event_cb_before(self, win, event):
        if event.keyval == keysyms.space:
            self.tdw.stop_drag(self.dragfunc_translate)
            self.tdw.stop_drag(self.dragfunc_rotate)
            return True
        return False

    def key_press_event_cb_after(self, win, event):
        key = event.keyval
        if self.fullscreen and key == keysyms.Escape: self.fullscreen_cb()
        else: return False
        return True
    def key_release_event_cb_after(self, win, event):
        return False

    def dragfunc_translate(self, dx, dy):
        self.tdw.scroll(-dx, -dy)

    def dragfunc_rotate(self, dx, dy):
        self.tdw.scroll(-dx, -dy, False)
        self.tdw.rotate(2*math.pi*dx/500.0)

    #def dragfunc_rotozoom(self, dx, dy):
    #    self.tdw.scroll(-dx, -dy, False)
    #    self.tdw.zoom(math.exp(-dy/100.0))
    #    self.tdw.rotate(2*math.pi*dx/500.0)

    def button_press_cb(self, win, event):
        #print event.device, event.button
        if event.type != gdk.BUTTON_PRESS:
            # ignore the extra double-click event
            return
        if event.button == 2:
            # check whether we are painting (accidental)
            pressure = event.get_axis(gdk.AXIS_PRESSURE)
            if (event.state & gdk.BUTTON1_MASK) or pressure:
                # do not allow dragging while painting (often happens accidentally)
                pass
            else:
                self.tdw.start_drag(self.dragfunc_translate)
        elif event.button == 1:
            if event.state & gdk.CONTROL_MASK:
                self.end_eraser_mode()
                self.colorpick_state.activate(event)
        elif event.button == 3:
            self.history_popup_state.activate(event)

    def button_release_cb(self, win, event):
        #print event.device, event.button
        if event.button == 2:
            self.tdw.stop_drag(self.dragfunc_translate)
        # too slow to be useful:
        #elif event.button == 3:
        #    self.tdw.stop_drag(self.dragfunc_rotate)

    def scroll_cb(self, win, event):
        d = event.direction
        if d == gdk.SCROLL_UP:
            if event.state & gdk.SHIFT_MASK:
                self.rotate('RotateLeft')
            else:
                self.zoom('ZoomIn')
        elif d == gdk.SCROLL_DOWN:
            if event.state & gdk.SHIFT_MASK:
                self.rotate('RotateRight')
            else:
                self.zoom('ZoomOut')
        elif d == gdk.SCROLL_LEFT:
            self.rotate('RotateRight')
        elif d == gdk.SCROLL_LEFT:
            self.rotate('RotateLeft')

    def clear_layer_cb(self, action):
        self.doc.clear_layer()
        if len(self.doc.layers) == 1:
            # this is like creating a new document:
            # make "save next" use a new file name
            self.filename = None
        
    def remove_layer_cb(self, action):
        if len(self.doc.layers) == 1:
            self.doc.clear_layer()
        else:
            self.doc.remove_layer()
            self.layerblink_state.activate(action)

    def layer_bg_cb(self, action):
        idx = self.doc.layer_idx - 1
        if idx < 0:
            return
        self.doc.select_layer(idx)
        self.layerblink_state.activate(action)

    def layer_fg_cb(self, action):
        idx = self.doc.layer_idx + 1
        if idx >= len(self.doc.layers):
            return
        self.doc.select_layer(idx)
        self.layerblink_state.activate(action)

    def pick_layer_cb(self, action):
        x, y = self.tdw.get_cursor_in_model_coordinates()
        for idx, layer in reversed(list(enumerate(self.doc.layers))):
            alpha = layer.surface.get_alpha (x, y, 5) * layer.opacity
            if alpha > 0.1:
                self.doc.select_layer(idx)
                self.layerblink_state.activate(action)
                return
        self.doc.select_layer(0)
        self.layerblink_state.activate(action)

    def pick_context_cb(self, action):
        x, y = self.tdw.get_cursor_in_model_coordinates()
        for idx, layer in reversed(list(enumerate(self.doc.layers))):
            alpha = layer.surface.get_alpha (x, y, 5) * layer.opacity
            if alpha > 0.1:
                old_layer = self.doc.layer
                self.doc.select_layer(idx)
                if self.doc.layer != old_layer:
                    self.layerblink_state.activate(action)

                # find the most recent (last) stroke that touches our picking point
                brush = self.doc.layer.get_brush_at(x, y)

                if brush:
                    # FIXME: clean brush concept?
                    self.app.brush.load_from_string(brush)
                    self.app.select_brush(None)
                else:
                    print 'Nothing found!'

                #self.app.brush.copy_settings_from(stroke.brush_settings)
                #self.app.select_brush()
                    
                return
        self.doc.select_layer(0)
        self.layerblink_state.activate(action)

    def layerblink_state_enter(self):
        self.tdw.current_layer_solo = True
        self.tdw.queue_draw()
    def layerblink_state_leave(self, reason):
        if self.layersolo_state.active:
            # FIXME: use state machine concept, maybe?
            return
        self.tdw.current_layer_solo = False
        self.tdw.queue_draw()
    def layersolo_state_enter(self):
        s = self.layerblink_state
        if s.active:
            s.leave()
        self.tdw.current_layer_solo = True
        self.tdw.queue_draw()
    def layersolo_state_leave(self, reason):
        self.tdw.current_layer_solo = False
        self.tdw.queue_draw()

    #def blink_layer_cb(self, action):
    #    self.layerblink_state.activate(action)

    def solo_layer_cb(self, action):
        self.layersolo_state.toggle(action)

    def new_layer_cb(self, action):
        insert_idx = self.doc.layer_idx
        if action.get_name() == 'NewLayerFG':
            insert_idx += 1
        self.doc.add_layer(insert_idx)
        self.layerblink_state.activate(action)

    @with_wait_cursor
    def merge_layer_cb(self, action):
        dst_idx = self.doc.layer_idx - 1
        if dst_idx < 0:
            return
        self.doc.merge_layer(dst_idx)
        self.layerblink_state.activate(action)

    def toggle_layers_above_cb(self, action):
        self.tdw.toggle_show_layers_above()

    def popup_cb(self, action):
        # This doesn't really belong here...
        # just because all popups are color popups now...
        # ...maybe should eraser_mode be a GUI state too?
        self.end_eraser_mode()

        state = self.popup_states[action.get_name()]
        state.activate(action)

    def eraser_cb(self, action):
        adj = self.app.brush_adjustment['eraser']
        if adj.get_value() > 0.9:
            self.end_eraser_mode()
        else:
            # enter eraser mode
            adj.set_value(1.0)
            adj2 = self.app.brush_adjustment['radius_logarithmic']
            r = adj2.get_value()
            self.eraser_mode_original_radius = r
            adj2.set_value(r + self.eraser_mode_radius_change)

    def end_eraser_mode(self):
        adj = self.app.brush_adjustment['eraser']
        if not adj.get_value() > 0.9:
            return
        adj.set_value(0.0)
        if self.eraser_mode_original_radius:
            # save eraser radius, restore old radius
            adj2 = self.app.brush_adjustment['radius_logarithmic']
            r = adj2.get_value()
            self.eraser_mode_radius_change = r - self.eraser_mode_original_radius
            adj2.set_value(self.eraser_mode_original_radius)
            self.eraser_mode_original_radius = None

    def device_changed_cb(self, old_device, new_device):
        # just enable eraser mode for now (TODO: remember full tool settings)
        # small problem with this code: it doesn't work well with brushes that have (eraser not in [1.0, 0.0])
        adj = self.app.brush_adjustment['eraser']
        if old_device is None and new_device.source != gdk.SOURCE_ERASER:
            # keep whatever startup brush was choosen
            return
        if new_device.source == gdk.SOURCE_ERASER:
            # enter eraser mode
            adj.set_value(1.0)
        elif new_device.source != gdk.SOURCE_ERASER and \
               (old_device is None or old_device.source == gdk.SOURCE_ERASER):
            # leave eraser mode
            adj.set_value(0.0)
        print 'device change:', new_device.name

    def brush_bigger_cb(self, action):
        adj = self.app.brush_adjustment['radius_logarithmic']
        adj.set_value(adj.get_value() + 0.3)
    def brush_smaller_cb(self, action):
        adj = self.app.brush_adjustment['radius_logarithmic']
        adj.set_value(adj.get_value() - 0.3)

    def more_opaque_cb(self, action):
        # FIXME: hm, looks this slider should be logarithmic?
        adj = self.app.brush_adjustment['opaque']
        adj.set_value(adj.get_value() * 1.8)
    def less_opaque_cb(self, action):
        adj = self.app.brush_adjustment['opaque']
        adj.set_value(adj.get_value() / 1.8)

    def brighter_cb(self, action):
        self.end_eraser_mode()
        h, s, v = self.app.brush.get_color_hsv()
        v += 0.08
        if v > 1.0: v = 1.0
        self.app.brush.set_color_hsv((h, s, v))
    def darker_cb(self, action):
        self.end_eraser_mode()
        h, s, v = self.app.brush.get_color_hsv()
        v -= 0.08
        if v < 0.0: v = 0.0
        self.app.brush.set_color_hsv((h, s, v))

    def layer_increase_opacity(self, action):
        opa = helpers.clamp(self.doc.layer.opacity + 0.08, 0.0, 1.0)
        self.doc.set_layer_opacity(opa)

    def layer_decrease_opacity(self, action):
        opa = helpers.clamp(self.doc.layer.opacity - 0.08, 0.0, 1.0)
        self.doc.set_layer_opacity(opa)
        
    @with_wait_cursor
    def open_file(self, filename):
        try:
            self.doc.load(filename)
        except document.SaveLoadError, e:
            self.app.message_dialog(str(e),type=gtk.MESSAGE_ERROR)
        else:
            self.filename = os.path.abspath(filename)
            print 'Loaded from', self.filename
            self.reset_view_cb(None)
            self.tdw.recenter_document()

    @with_wait_cursor
    def save_file(self, filename, **options):
        try:
            x, y, w, h =  self.doc.get_bbox()
            if w == 0 and h == 0:
                raise document.SaveLoadError, _('Did not save, the canvas is empty.')
            self.doc.save(filename, **options)
        except document.SaveLoadError, e:
            self.app.message_dialog(str(e),type=gtk.MESSAGE_ERROR)
        else:
            self.filename = os.path.abspath(filename)
            print 'Saved to', self.filename
            self.save_history.append(os.path.abspath(filename))
            self.save_history = self.save_history[-100:]
            f = open(os.path.join(self.app.confpath, 'save_history.conf'), 'w')
            f.write('\n'.join(self.save_history))
            ## tell other gtk applications
            ## (hm, is there any application that uses this at all? or is the code below wrong?)
            #manager = gtk.recent_manager_get_default()
            #manager.add_item(os.path.abspath(filename))

    def confirm_destructive_action(self, title='Confirm', question='Really continue?'):
        t = self.doc.unsaved_painting_time
        if t < 30:
            # no need to ask
            return True

        if t > 120:
            t = _('%d minutes') % (t/60)
        else:
            t = _('%d seconds') % t
        d = gtk.Dialog(title, self, gtk.DIALOG_MODAL)

        b = d.add_button(gtk.STOCK_DISCARD, gtk.RESPONSE_OK)
        b.set_image(gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_BUTTON))
        d.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        b = d.add_button(_("_Save as Scrap"), gtk.RESPONSE_APPLY)
        b.set_image(gtk.image_new_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_BUTTON))

        d.set_has_separator(False)
        d.set_default_response(gtk.RESPONSE_CANCEL)
        l = gtk.Label()
        l.set_markup(_("<b>%s</b>\n\nThis will discard %s of unsaved painting.") % (question,t))
        l.set_padding(10, 10)
        l.show()
        d.vbox.pack_start(l)
        response = d.run()
        d.destroy()
        if response == gtk.RESPONSE_APPLY:
            self.save_scrap_cb(None)
            return True
        return response == gtk.RESPONSE_OK

    def new_cb(self, action):
        if not self.confirm_destructive_action():
            return
        bg = self.doc.background
        self.doc.clear()
        self.doc.set_background(bg)
        self.filename = None

    def open_cb(self, action):
        if not self.confirm_destructive_action():
            return
        dialog = gtk.FileChooserDialog(_("Open..."), self,
                                       gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)

        filters = [ #name, patterns
        (_("All Recognized Formats"), ("*.ora", "*.png", "*.jpg", "*.jpeg")),
        (_("OpenRaster (*.ora)"), ("*.ora",)),
        (_("PNG (*.png)"), ("*.png",)),
        (_("JPEG (*.jpg; *.jpeg)"), ("*.jpg", "*.jpeg")),
        ]
        for name, patterns in filters:
            f = gtk.FileFilter()
            f.set_name(name)
            for p in patterns:
                f.add_pattern(p)
            dialog.add_filter(f)

        if self.filename:
            dialog.set_filename(self.filename)
        try:
            if dialog.run() == gtk.RESPONSE_OK:
                self.open_file(dialog.get_filename())
        finally:
            dialog.destroy()

    def save_cb(self, action):
        if not self.filename:
            self.save_as_cb(action)
        else:
            self.save_file(self.filename)


    def init_save_dialog(self):
        dialog = gtk.FileChooserDialog(_("Save.."), self,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        self.save_dialog = dialog
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_do_overwrite_confirmation(True)

        filter2info = {}
        self.filter2info = filter2info

        filters = [ #name, patterns, saveopts
        (_("Any format (prefer OpenRaster)"), ("*.ora", "*.png", "*.jpg", "*.jpeg"), ('.ora', {})),
        (_("OpenRaster (*.ora)"), ("*.ora", ), ('.ora', {})),
        ("PNG solid with background (*.png)", ("*.png", ), ('.png', {'alpha': False})),
        (_("PNG transparent (*.png)"), ("*.png", ), ('.png', {'alpha': True})),
        (_("Multiple PNG transparent (*.XXX.png)"), ("*.png", ), ('.png', {'multifile': True})),
        (_("JPEG 90% quality (*.jpg; *.jpeg)"), ("*.jpg", "*.jpeg"), ('.jpg', {'quality': 90})),
        ]
        for nr, filt in enumerate(filters):
            name, patterns, saveopts = filt
            f = gtk.FileFilter()
            filter2info[f] = saveopts
            f.set_name(name)
            for pat in patterns:
                f.add_pattern(pat)
            dialog.add_filter(f)
            if nr == 0:
                self.save_filter_default = f

    def save_as_cb(self, action):
        dialog = self.save_dialog

        def dialog_set_filename(s):
            # According to pygtk docu we should use set_filename(),
            # however doing so removes the selected filefilter.
            path, name = os.path.split(s)
            dialog.set_current_folder(path)
            dialog.set_current_name(name)

        if self.filename:
            dialog_set_filename(self.filename)
        else:
            dialog_set_filename('')
            dialog.set_filter(self.save_filter_default)

        try:
            while dialog.run() == gtk.RESPONSE_OK:

                filename = dialog.get_filename()
                name, ext = os.path.splitext(filename)
                ext_filter, options = self.filter2info.get(dialog.get_filter(), ('ora', {}))

                if ext:
                    if ext_filter != ext:
                        # Minor ugliness: if the user types '.png' but
                        # leaves the default .ora filter selected, we
                        # use the default options instead of those
                        # above. However, they are the same at the moment.
                        options = {}
                    assert(filename)
                    self.save_file(filename, **options)
                    break
                
                # add proper extension
                filename = name + ext_filter

                # trigger overwrite confirmation for the modified filename
                dialog_set_filename(filename)
                dialog.response(gtk.RESPONSE_OK)

        finally:
            dialog.hide()

    def save_scrap_cb(self, action):
        filename = self.filename
        prefix = self.app.settingsWindow.save_scrap_prefix

        number = None
        if filename:
            l = re.findall(re.escape(prefix) + '([0-9]+)', filename)
            if l:
                number = l[0]

        if number:
            # reuse the number, find the next character
            char = 'a'
            for filename in glob(prefix + number + '_*'):
                c = filename[len(prefix + number + '_')]
                if c >= 'a' and c <= 'z' and c >= char:
                    char = chr(ord(c)+1)
            if char > 'z':
                # out of characters, increase the number
                self.filename = None
                return self.save_scrap_cb(action)
            filename = '%s%s_%c' % (prefix, number, char)
        else:
            # we don't have a scrap filename yet, find the next number
            maximum = 0
            for filename in glob(prefix + '[0-9][0-9][0-9]*'):
                filename = filename[len(prefix):]
                res = re.findall(r'[0-9]*', filename)
                if not res: continue
                number = int(res[0])
                if number > maximum:
                    maximum = number
            filename = '%s%03d_a' % (prefix, maximum+1)

        #if self.doc.is_layered():
        #    filename += '.ora'
        #else:
        #    filename += '.png'
        filename += '.ora'

        assert not os.path.exists(filename)
        self.save_file(filename)

    def open_recent_cb(self, action):
        # feed history with scrap directory (mainly for initial history)
        prefix = self.app.settingsWindow.save_scrap_prefix
        prefix = os.path.abspath(prefix)
        l = glob(prefix + '*.png') + glob(prefix + '*.ora') + glob(prefix + '*.jpg') + glob(prefix + '*.jpeg')
        l = [x for x in l if x not in self.save_history]
        l = l + self.save_history
        l = [x for x in l if os.path.exists(x)]
        l.sort(key=os.path.getmtime)
        self.save_history = l

        # pick the next most recent file from the history
        idx = -1
        if self.filename in self.save_history:
            def basename(filename):
                return os.path.splitext(filename)[0]
            idx = self.save_history.index(self.filename)
            while basename(self.save_history[idx]) == basename(self.filename):
                idx -= 1
                if idx == -1:
                    return

        if not self.confirm_destructive_action():
            return
        if not self.save_history:
            self.app.message_dialog(_('There are no existing images in the save history. Did you move them all away?'), gtk.MESSAGE_WARNING)
            return

        self.open_file(self.save_history[idx])

    def quit_cb(self, *trash):
        self.doc.split_stroke()
        self.app.save_gui_config() # FIXME: should do this periodically, not only on quit

        if not self.confirm_destructive_action(title=_('Quit'), question=_('Really Quit?')):
            return True

        gtk.main_quit()
        return False

    def zoom_cb(self, action):
        self.zoom(action.get_name())
    def rotate_cb(self, action):
        self.rotate(action.get_name())
    def flip_cb(self, action):
        self.tdw.set_flipped(action.get_active())

    def move(self, command):
        self.doc.split_stroke()
        step = min(self.tdw.window.get_size()) / 5
        if   command == 'MoveLeft' : self.tdw.scroll(-step, 0)
        elif command == 'MoveRight': self.tdw.scroll(+step, 0)
        elif command == 'MoveUp'   : self.tdw.scroll(0, -step)
        elif command == 'MoveDown' : self.tdw.scroll(0, +step)
        else: assert 0

    def zoom(self, command):
        if   command == 'ZoomIn' : self.zoomlevel += 1
        elif command == 'ZoomOut': self.zoomlevel -= 1
        else: assert 0
        if self.zoomlevel < 0: self.zoomlevel = 0
        if self.zoomlevel >= len(self.zoomlevel_values): self.zoomlevel = len(self.zoomlevel_values) - 1
        z = self.zoomlevel_values[self.zoomlevel]
        self.tdw.set_zoom(z)

    def rotate(self, command):
        if   command == 'RotateRight': self.tdw.rotate(+2*math.pi/14)
        elif command == 'RotateLeft' : self.tdw.rotate(-2*math.pi/14)
        else: assert 0

    def reset_view_cb(self, command):
        self.tdw.set_rotation(0.0)
        self.zoomlevel = self.zoomlevel_values.index(1.0)
        self.tdw.set_zoom(1.0)
        self.tdw.set_flipped(False)
        self.action_group.get_action('Flip').set_active(False)

    def fullscreen_cb(self, *trash):
        # note: there is some ugly flickering when toggling fullscreen
        #       self.window.begin_paint/end_paint does not help against it
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            x, y = self.get_position()
            w, h = self.get_size()
            self.geometry_before_fullscreen = (x, y, w, h)
            self.menubar.hide()
            self.window.fullscreen()
            #self.tdw.set_scroll_at_edges(True)
        else:
            self.window.unfullscreen()
            self.menubar.show()
            #self.tdw.set_scroll_at_edges(False)
            del self.geometry_before_fullscreen

    def context_cb(self, action):
        # TODO: this context-thing is not very useful like that, is it?
        #       You overwrite your settings too easy by accident.
        # - not storing settings under certain circumstances?
        # - think about other stuff... brush history, only those actually used, etc...
        name = action.get_name()
        store = False
        if name == 'ContextStore':
            context = self.app.selected_context
            if not context:
                print 'No context was selected, ignoring store command.'
                return
            store = True
        else:
            if name.endswith('s'):
                store = True
                name = name[:-1]
            i = int(name[-2:])
            context = self.app.contexts[i]
        self.app.selected_context = context
        if store:
            context.copy_settings_from(self.app.brush)
            preview = self.app.brushSelectionWindow.get_preview_pixbuf()
            context.update_preview(preview)
            context.save()
        else: # restore
            self.app.select_brush(context)
            self.app.brushSelectionWindow.set_preview_pixbuf(context.preview)

    def show_infodialog_cb(self, action):
        text = {
        'ShortcutHelp': 
                _("Move your mouse over a menu entry, then press the key to assign."),
        'ViewHelp': 
                _("You can also drag the canvas with the mouse while holding the middle "
                "mouse button or spacebar. Or with the arrow keys."
                "\n\n"
                "In contrast to earlier versions, scrolling and zooming are harmless now and "
                "will not make you run out of memory. But you still require a lot of memory "
                "if you paint all over while fully zoomed out."),
        'ContextHelp':
                _("This is used to quickly save/restore brush settings "
                 "using keyboard shortcuts. You can paint with one hand and "
                 "change brushes with the other without interrupting."
                 "\n\n"
                 "There are 10 memory slots to hold brush settings.\n"
                 "Those are annonymous "
                 "brushes, they are not visible in the brush selector list. "
                 "But they will stay even if you quit. "
                 "They will also remember the selected color. In contrast, selecting a "
                 "normal brush never changes the color. "),
        'Docu':
                _("There is a tutorial available "
                 "on the MyPaint homepage. It explains some features which are "
                 "hard to discover yourself.\n\n"
                 "Comments about the brush settings (opaque, hardness, etc.) and "
                 "inputs (pressure, speed, etc.) are available as tooltips. "
                 "Put your mouse over a label to see them. "
                 "\n"),
        'About':
                _(u"MyPaint %s - pressure sensitive painting application\n") % MYPAINT_VERSION +
                u"Copyright (C) 2005-2009\n"
                u"Martin Renold &lt;martinxyz@gmx.ch&gt;\n\n" + 
                _(u"Contributors:\n") + 
                u"Artis Rozentāls &lt;artis@aaa.apollo.lv&gt; (brushes)\n"
                u"Yves Combe &lt;yves@ycombe.net&gt; (portability)\n"
                u"Sebastian Kraft (desktop icon)\n"
                u"Popolon &lt;popolon@popolon.org&gt; (brushes, programming)\n"
                u"Clement Skau &lt;clementskau@gmail.com&gt; (programming)\n"
                u'Marcelo "Tanda" Cerviño &lt;info@lodetanda.com.ar&gt; (patterns, brushes)\n'
                u'Jon Nordby &lt;jononor@gmail.com&gt; (programming)\n'
                u'Álinson Santos &lt;isoron@gmail.com&gt; (programming)\n'
                u'Tumagonx &lt;mr.tiar@gmail.com&gt; (portability)\n'
                u'Ilya Portnov &lt;portnov84@rambler.ru&gt; (programming, i18n)\n'
                u"\n" + 
                _(u"This program is free software; you can redistribute it and/or modify "
                u"it under the terms of the GNU General Public License as published by "
                u"the Free Software Foundation; either version 2 of the License, or "
                u"(at your option) any later version.\n"
                u"\n"
                u"This program is distributed in the hope that it will be useful, "
                u"but WITHOUT ANY WARRANTY. See the COPYING file for more details.")
        }
        self.app.message_dialog(text[action.get_name()])

