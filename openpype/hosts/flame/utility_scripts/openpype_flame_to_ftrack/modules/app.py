import os
from PySide2 import QtWidgets, QtCore
import uiwidgets
import flame

from .ftrack_lib import (
    maintained_ftrack_session,
    FtrackEntityOperator,
    FtrackComponentCreator
)
from .utils import (
    get_config,
    set_config,
    get_all_task_types,
    make_temp_dir,
    export_thumbnail,
    export_video,
    timecode_to_frames
)
from pprint import pformat


class FlameToFtrackPanel(QtWidgets.QWidget()):
    temp_data_dir = None
    project_entity = None
    task_types = {}
    all_task_types = {}
    processed_components = []

    # TreeWidget
    columns = {
        "Sequence name": {
            "columnWidth": 200,
            "order": 0
        },
        "Shot name": {
            "columnWidth": 200,
            "order": 1
        },
        "Clip duration": {
            "columnWidth": 100,
            "order": 2
        },
        "Shot description": {
            "columnWidth": 500,
            "order": 3
        },
        "Task description": {
            "columnWidth": 500,
            "order": 4
        },
    }

    def __init__(self, selection, *args, **kwargs):
        super(FlameToFtrackPanel, self).__init__(*args, **kwargs)

        self.selection = selection
        # creating ui
        self.setMinimumSize(1500, 600)
        self.setWindowTitle('Sequence Shots to Ftrack')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet('background-color: #313131')


        self._create_tree_widget()
        self._set_sequence_params()

        self._create_project_widget()

        self._generate_widgets()

        self._generate_layouts()

        self._timeline_info()

        self._fix_resolution()

    def _generate_widgets(self):
        with get_config("main") as cfg_d:
            self._create_task_type_widget(cfg_d)

            # input fields
            self.shot_name_label = uiwidgets.FlameLabel(
                'Shot name template', 'normal', self)
            self.shot_name_template_input = uiwidgets.FlameLineEdit(
                cfg_d["shot_name_template"], self)

            self.hierarchy_label = uiwidgets.FlameLabel(
                'Parents template', 'normal', self)
            self.hierarchy_template_input = uiwidgets.FlameLineEdit(
                cfg_d["hierarchy_template"], self)

            self.start_frame_label = uiwidgets.FlameLabel(
                'Workfile start frame', 'normal', self)
            self.start_frame_input = uiwidgets.FlameLineEdit(
                cfg_d["workfile_start_frame"], self)

            self.handles_label = uiwidgets.FlameLabel(
                'Shot handles', 'normal', self)
            self.handles_input = uiwidgets.FlameLineEdit(
                cfg_d["shot_handles"], self)

            self.width_label = uiwidgets.FlameLabel(
                'Sequence width', 'normal', self)
            self.width_input = uiwidgets.FlameLineEdit(
                str(self.seq_width), self)

            self.height_label = uiwidgets.FlameLabel(
                'Sequence height', 'normal', self)
            self.height_input = uiwidgets.FlameLineEdit(
                str(self.seq_height), self)

            self.pixel_aspect_label = uiwidgets.FlameLabel(
                'Pixel aspect ratio', 'normal', self)
            self.pixel_aspect_input = uiwidgets.FlameLineEdit(
                str(1.00), self)

            self.fps_label = uiwidgets.FlameLabel(
                'Frame rate', 'normal', self)
            self.fps_input = uiwidgets.FlameLineEdit(
                str(self.fps), self)

            # Button
            self.select_all_btn = uiwidgets.FlameButton(
                'Select All', self.select_all, self)

            self.remove_temp_data_btn = uiwidgets.FlameButton(
                'Remove temp data', self.remove_temp_data, self)

            self.ftrack_send_btn = uiwidgets.FlameButton(
                'Send to Ftrack', self._send_to_ftrack, self)

    def _generate_layouts(self):
        # left props
        v_shift = 0
        prop_layout_l = QtWidgets.QGridLayout()
        prop_layout_l.setHorizontalSpacing(30)
        if self.project_selector_enabled:
            prop_layout_l.addWidget(self.project_select_label, v_shift, 0)
            prop_layout_l.addWidget(self.project_select_input, v_shift, 1)
            v_shift += 1
        prop_layout_l.addWidget(self.shot_name_label, (v_shift + 0), 0)
        prop_layout_l.addWidget(
            self.shot_name_template_input, (v_shift + 0), 1)
        prop_layout_l.addWidget(self.hierarchy_label, (v_shift + 1), 0)
        prop_layout_l.addWidget(
            self.hierarchy_template_input, (v_shift + 1), 1)
        prop_layout_l.addWidget(self.start_frame_label, (v_shift + 2), 0)
        prop_layout_l.addWidget(self.start_frame_input, (v_shift + 2), 1)
        prop_layout_l.addWidget(self.handles_label, (v_shift + 3), 0)
        prop_layout_l.addWidget(self.handles_input, (v_shift + 3), 1)
        prop_layout_l.addWidget(self.task_type_label, (v_shift + 4), 0)
        prop_layout_l.addWidget(
            self.task_type_input, (v_shift + 4), 1)

        # right props
        prop_widget_r = QtWidgets.QWidget(self)
        prop_layout_r = QtWidgets.QGridLayout(prop_widget_r)
        prop_layout_r.setHorizontalSpacing(30)
        prop_layout_r.setAlignment(
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        prop_layout_r.setContentsMargins(0, 0, 0, 0)
        prop_layout_r.addWidget(self.width_label, 1, 0)
        prop_layout_r.addWidget(self.width_input, 1, 1)
        prop_layout_r.addWidget(self.height_label, 2, 0)
        prop_layout_r.addWidget(self.height_input, 2, 1)
        prop_layout_r.addWidget(self.pixel_aspect_label, 3, 0)
        prop_layout_r.addWidget(self.pixel_aspect_input, 3, 1)
        prop_layout_r.addWidget(self.fps_label, 4, 0)
        prop_layout_r.addWidget(self.fps_input, 4, 1)

        # prop layout
        prop_main_layout = QtWidgets.QHBoxLayout()
        prop_main_layout.addLayout(prop_layout_l, 1)
        prop_main_layout.addSpacing(20)
        prop_main_layout.addWidget(prop_widget_r, 1)

        # buttons layout
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.remove_temp_data_btn)
        hbox.addWidget(self.select_all_btn)
        hbox.addWidget(self.ftrack_send_btn)

        # put all layouts together
        main_frame = QtWidgets.QVBoxLayout(self)
        main_frame.setMargin(20)
        main_frame.addLayout(prop_main_layout)
        main_frame.addWidget(self.tree)
        main_frame.addLayout(hbox)

    def _set_sequence_params(self):
        for select in self.selection:
            self.seq_height = select.height
            self.seq_width = select.width
            self.fps = float(str(select.frame_rate)[:-4])
            break

    def _create_task_type_widget(self, cfg_d):
        self.task_types = get_all_task_types(self.project_entity)

        self.task_type_label = uiwidgets.FlameLabel(
            'Create Task (type)', 'normal', self)
        self.task_type_input = uiwidgets.FlamePushButtonMenu(
            cfg_d["create_task_type"], self.task_types.keys(), self)

    def _create_project_widget(self):

        with maintained_ftrack_session() as session:
            # get project name from flame current project
            self.project_name = flame.project.current_project.name

            # get project from ftrack -
            # ftrack project name has to be the same as flame project!
            query = 'Project where full_name is "{}"'.format(self.project_name)

            # globally used variables
            self.project_entity = session.query(query).first()

            self.project_selector_enabled = bool(not self.project_entity)

            if self.project_selector_enabled:
                self.all_projects = session.query(
                    "Project where status is active").all()
                self.project_entity = self.all_projects[0]
                project_names = [p["full_name"] for p in self.all_projects]
                self.all_task_types = {p["full_name"]: get_all_task_types(
                    p).keys() for p in self.all_projects}
                self.project_select_label = uiwidgets.FlameLabel(
                    'Select Ftrack project', 'normal', self)
                self.project_select_input = uiwidgets.FlamePushButtonMenu(
                    self.project_entity["full_name"], project_names, self)
                self.project_select_input.selection_changed.connect(
                    self._on_project_changed)

    def _create_tree_widget(self):
        ordered_column_labels = self.columns.keys()
        for _name, _value in self.columns.items():
            ordered_column_labels.pop(_value["order"])
            ordered_column_labels.insert(_value["order"], _name)

        self.tree = uiwidgets.FlameTreeWidget(ordered_column_labels, self)

        # Allow multiple items in tree to be selected
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)

        # Set tree column width
        for _name, _val in self.columns.items():
            self.tree.setColumnWidth(
                _val["order"],
                _val["columnWidth"]
            )

        # Prevent weird characters when shrinking tree columns
        self.tree.setTextElideMode(QtCore.Qt.ElideNone)

    def _send_to_ftrack(self):
        # resolve active project and add it to self.project_entity
        if self.project_selector_enabled:
            selected_project_name = self.project_select_input.text()
            self.project_entity = next(
                (p for p in self.all_projects
                    if p["full_name"] in selected_project_name),
                None
            )

        _cfg_data_back = {}

        # get shot name template from gui input
        shot_name_template = self.shot_name_template_input.text()

        # get hierarchy from gui input
        hierarchy_text = self.hierarchy_template_input.text()

        # get hanldes from gui input
        handles = self.handles_input.text()

        # get frame start from gui input
        frame_start = int(self.start_frame_input.text())

        # get task type from gui input
        task_type = self.task_type_input.text()

        # get resolution from gui inputs
        width = self.width_input.text()
        height = self.height_input.text()
        pixel_aspect = self.pixel_aspect_input.text()
        fps = self.fps_input.text()

        _cfg_data_back = {
            "shot_name_template": shot_name_template,
            "workfile_start_frame": str(frame_start),
            "shot_handles": handles,
            "hierarchy_template": hierarchy_text,
            "create_task_type": task_type
        }

        # add cfg data back to settings.ini
        set_config(_cfg_data_back, "main")

        with maintained_ftrack_session() as session:
            print("Ftrack session is: {}".format(session))

            entity_operator = FtrackEntityOperator(
                session, self.project_entity)
            component_creator = FtrackComponentCreator(session)

            self.generate_temp_data({
                "nbHandles": handles
            })

            temp_files = os.listdir(self.temp_data_dir)
            thumbnails = [f for f in temp_files if "jpg" in f]
            videos = [f for f in temp_files if "mov" in f]

            print(temp_files)
            print(thumbnails)
            print(videos)

            # Get all selected items from treewidget
            for item in self.tree.selectedItems():
                # frame ranges
                frame_duration = int(item.text(2))
                frame_end = frame_start + frame_duration

                # description
                shot_description = item.text(3)
                task_description = item.text(4)

                # other
                sequence_name = item.text(0)
                shot_name = item.text(1)

                # get component files
                thumb_f = next((f for f in thumbnails if shot_name in f), None)
                video_f = next((f for f in videos if shot_name in f), None)
                thumb_fp = os.path.join(self.temp_data_dir, thumb_f)
                video_fp = os.path.join(self.temp_data_dir, video_f)
                print(thumb_fp)
                print(video_fp)

                print("processed comps: {}".format(self.processed_components))
                processed = False
                if thumb_f not in self.processed_components:
                    self.processed_components.append(thumb_f)
                else:
                    processed = True

                print("processed: {}".format(processed))

                # populate full shot info
                shot_attributes = {
                    "sequence": sequence_name,
                    "shot": shot_name,
                    "task": task_type
                }

                # format shot name template
                _shot_name = shot_name_template.format(**shot_attributes)

                # format hierarchy template
                _hierarchy_text = hierarchy_text.format(**shot_attributes)
                print(_hierarchy_text)

                # solve parents
                parents = entity_operator.create_parents(_hierarchy_text)
                print(parents)

                # obtain shot parents entities
                _parent = None
                for _name, _type in parents:
                    p_entity = entity_operator.get_ftrack_entity(
                        session,
                        _type,
                        _name,
                        _parent
                    )
                    print(p_entity)
                    _parent = p_entity

                # obtain shot ftrack entity
                f_s_entity = entity_operator.get_ftrack_entity(
                    session,
                    "Shot",
                    _shot_name,
                    _parent
                )
                print("Shot entity is: {}".format(f_s_entity))

                if not processed:
                    # first create thumbnail and get version entity
                    assetversion_entity = component_creator.create_comonent(
                        f_s_entity, {
                            "file_path": thumb_fp
                        }
                    )

                    # secondly add video to version entity
                    component_creator.create_comonent(
                        f_s_entity, {
                            "file_path": video_fp,
                            "duration": frame_duration,
                            "handles": int(handles),
                            "fps": float(fps)
                        }, assetversion_entity
                    )

                # create custom attributtes
                custom_attrs = {
                    "frameStart": frame_start,
                    "frameEnd": frame_end,
                    "handleStart": int(handles),
                    "handleEnd": int(handles),
                    "resolutionWidth": int(width),
                    "resolutionHeight": int(height),
                    "pixelAspect": float(pixel_aspect),
                    "fps": float(fps)
                }

                # update custom attributes on shot entity
                for key in custom_attrs:
                    f_s_entity['custom_attributes'][key] = custom_attrs[key]

                task_entity = entity_operator.create_task(
                    task_type, self.task_types, f_s_entity)

                # Create notes.
                user = session.query(
                    "User where username is \"{}\"".format(session.api_user)
                ).first()

                f_s_entity.create_note(shot_description, author=user)

                if task_description:
                    task_entity.create_note(task_description, user)

                entity_operator.commit()

            component_creator.close()

    def _fix_resolution(self):
        # Center window in linux
        resolution = QtWidgets.QDesktopWidget().screenGeometry()
        self.move(
            (resolution.width() / 2) - (self.frameSize().width() / 2),
            (resolution.height() / 2) - (self.frameSize().height() / 2))

    def _on_project_changed(self):
        task_types = self.all_task_types[self.project_name]
        self.task_type_input.set_menu_options(task_types)

    def _timeline_info(self):
        # identificar as informacoes dos segmentos na timeline
        for sequence in self.selection:
            frame_rate = float(str(sequence.frame_rate)[:-4])
            for ver in sequence.versions:
                for tracks in ver.tracks:
                    for segment in tracks.segments:
                        print(segment.attributes)
                        if str(segment.name)[1:-1] == "":
                            continue
                        # get clip frame duration
                        record_duration = str(segment.record_duration)[1:-1]
                        clip_duration = timecode_to_frames(
                            record_duration, frame_rate)

                        # populate shot source metadata
                        shot_description = ""
                        for attr in ["tape_name", "source_name", "head",
                                     "tail", "file_path"]:
                            if not hasattr(segment, attr):
                                continue
                            _value = getattr(segment, attr)
                            _label = attr.replace("_", " ").capitalize()
                            row = "{}: {}\n".format(_label, _value)
                            shot_description += row

                        # Add timeline segment to tree
                        QtWidgets.QTreeWidgetItem(self.tree, [
                            str(sequence.name)[1:-1],  # seq
                            str(segment.name)[1:-1],  # shot
                            str(clip_duration),  # clip duration
                            shot_description,  # shot description
                            str(segment.comment)[1:-1]  # task description
                        ]).setFlags(
                            QtCore.Qt.ItemIsEditable
                            | QtCore.Qt.ItemIsEnabled
                            | QtCore.Qt.ItemIsSelectable
                        )

        # Select top item in tree
        self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def select_all(self, ):
        self.tree.selectAll()

    def remove_temp_data(self, ):
        import shutil

        if self.temp_data_dir:
            shutil.rmtree(self.temp_data_dir)
        self.temp_data_dir = None

    def generate_temp_data(self, change_preset_data):
        if self.temp_data_dir:
            return True

        with make_temp_dir() as tempdir_path:
            for seq in self.selection:
                export_thumbnail(seq, tempdir_path, change_preset_data)
                export_video(seq, tempdir_path, change_preset_data)
                self.temp_data_dir = tempdir_path
                break
