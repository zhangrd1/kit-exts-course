import omni.ext
from pxr import Usd, UsdGeom
import omni.ui as ui
import omni.kit.commands


WARNINGS = "Something Wrong with Your Hierarchy!"
MAX_LENGTH = 1000


class XsuperzoneTeachExploded_viewExtension(omni.ext.IExt):
    def __init__(self):
        self._stage = omni.usd.get_context().get_stage()
        self.x_mesh = None
        self.y_mesh = None
        self.z_mesh = None

    def on_startup(self, ext_id):
        print("[xsuperzone.teach.exploded_view] exploded_view startup")

        self._window = ui.Window(
            "Exploded-View",
            width=400,
            height=200,
        )

        axis = ["X", "Y", "Z"]

        with self._window.frame:
            with ui.HStack():
                with ui.VStack(width=100):
                    ui.Button(
                        "Select Prims",
                        tooltip="Please select the Primitives you want to Explode",
                        clicked_fn=self.select_prim
                    )
                    ui.Button(
                        "Reset", 
                        tooltip="Clear all the data you Set",
                        clicked_fn=self.reset
                    )

                with ui.VStack(width=50):
                    for i in axis:
                        ui.Label(
                            i,
                            tooltip=f"Please decide the max distance of {i}-axis your primitive will reach"
                        )

                with ui.VStack(width=50):  
                    self.drag_x = ui.IntField()
                    self.drag_y = ui.IntField()
                    self.drag_z = ui.IntField()

                with ui.VStack():
                    self.slider_x = ui.IntSlider(min=0, max=MAX_LENGTH)
                    self.slider_y = ui.IntSlider(min=0, max=MAX_LENGTH)
                    self.slider_z = ui.IntSlider(min=0, max=MAX_LENGTH)

                    self.slider_x.model = self.drag_x.model
                    self.slider_y.model = self.drag_y.model
                    self.slider_z.model = self.drag_z.model

                    self.slider_x.model.add_value_changed_fn(
                        lambda m: self.prim_translate('x', m)
                    )
                    self.slider_y.model.add_value_changed_fn(
                        lambda m: self.prim_translate('y', m)
                    )
                    self.slider_z.model.add_value_changed_fn(
                        lambda m: self.prim_translate('z', m)
                    )

    def on_shutdown(self):
        print("[xsuperzone.teach.exploded_view] exploded_view shutdown")

    def reset(self):
        self.drag_x.model.set_value(0)
        self.drag_y.model.set_value(0)
        self.drag_z.model.set_value(0)

        if self.x_mesh:
            for mesh in self.x_mesh:
                xform = mesh.GetParent()
                UsdGeom.XformCommonAPI(xform).SetTranslate((0,0,0))
            self.x_mesh.clear()
            self.y_mesh.clear()
            self.z_mesh.clear()

    def select_prim(self):
        """
        将所要爆炸的 mesh 保存到 self.xyz_mesh:list 中
        """

        self.reset()

        # 获取用户选择的path，这个path是需要便利的根节点，没有任何选择则退出
        geo_selected_path: list = omni.usd.get_context().get_selection().get_selected_prim_paths()

        if not geo_selected_path:
            print("Please select something!!!")
            return None

        # 根据选择的 path 找到 根节点的 prim
        self._selected_root: Usd.Prim = self._stage.GetPrimAtPath(geo_selected_path[0])

        # 接受所有遍历到的mesh
        self.meshes_select = []

        # 添加所有子mesh到列表
        self.get_sturctured(self._selected_root)
        print(self.meshes_select)

        print("-" * 20, "Hierarchy Structured Sucessfully", "-" * 20)

        if not self.meshes_select:
            print(WARNINGS, ", Caused by Nothing is mesh")
            return None

        self.x_mesh, self.y_mesh, self.z_mesh = self.sort_mesh_by_axis(self.meshes_select)
        
        print("-" * 20, "Select Sucessfully", "-" * 20)

        return None

    def get_sturctured(self, root):
        '''
        构建一个层次结构，永远是：xform-mesh的结构
        '''
        for child in root.GetChildren():
            if UsdGeom.Mesh(child):
                if UsdGeom.Xform(child.GetParent()):
                    if child.GetParent() != self._selected_root:
                        self.meshes_select.append(child)
                    else:
                        xform_name = child.GetName() + '_xform'
                        xform_path = child.GetParent().GetPath().pathString + f'/{xform_name}'
                        UsdGeom.Xform.Define(self._stage, xform_path)

                        omni.kit.commands.execute(
                            'MovePrim',
                            path_from=child.GetPath(),
                            path_to=xform_path + f'/{child.GetName()}',
                            keep_world_transform=False,
                            destructive=False)
                        
                        self.meshes_select.append(child)

            else:
                self.get_sturctured(child)

    def sort_mesh_by_axis(self, meshes: list) -> dict:
        """
        获取 mesh 的位置（通过取第一个顶点实现）
        计算好每个 mesh 距离中心的百分比
        最终根据xyz轴分别排序好{Prim:percent}
        """
        x_mesh = {}
        y_mesh = {}
        z_mesh = {}

        for mesh in meshes:
            # meshes_info[mesh] = mesh.GetAttribute('points').Get()
            points:list = mesh.GetAttribute('points').Get()
            if points:
                x_mesh[mesh] = points[0][0]
                y_mesh[mesh] = points[0][1]
                z_mesh[mesh] = points[0][2]
            else:
                meshes.remove(mesh)

        x_mesh = self.get_dis_percent(x_mesh)
        y_mesh = self.get_dis_percent(y_mesh)
        z_mesh = self.get_dis_percent(z_mesh)

        return x_mesh, y_mesh, z_mesh

    def get_dis_percent(self, mesh_list):
        distance = list(mesh_list.values())
        distance = sorted(distance)
        length = max(distance) - min(distance)
        mid_dis = distance[len(distance) // 2]

        for i in mesh_list:
            dis_percent = (mesh_list[i] - mid_dis) / length
            mesh_list[i] = dis_percent

        return mesh_list

    def prim_translate(self, dim:str, model):
        """
        输入：dict{prim:(维度的距离百分比)}
        输出：None，把每个prim进行独特的位移
        """
        
        if dim == 'x':
            for mesh in self.x_mesh:
                xform = mesh.GetParent()
                new_trans = self.x_mesh[mesh] * model.get_value_as_float()
                origin_pos = xform.GetAttribute('xformOp:translate').Get()
                if not origin_pos:
                    origin_pos = [0,0,0]

                UsdGeom.XformCommonAPI(xform).SetTranslate((
                    new_trans,
                    origin_pos[1],
                    origin_pos[2]
                    ))
        elif dim == 'y':
            for mesh in self.y_mesh:
                xform = mesh.GetParent()
                new_trans = self.y_mesh[mesh] * model.get_value_as_float()
                origin_pos = xform.GetAttribute('xformOp:translate').Get()
                if not origin_pos:
                    origin_pos = [0,0,0]
                
                UsdGeom.XformCommonAPI(xform).SetTranslate((
                    origin_pos[0],
                    new_trans,
                    origin_pos[2]
                    ))
        if dim == 'z':
            for mesh in self.z_mesh:
                xform = mesh.GetParent()
                new_trans = self.z_mesh[mesh] * model.get_value_as_float()
                origin_pos = xform.GetAttribute('xformOp:translate').Get()
                if not origin_pos:
                    origin_pos = [0,0,0]
                
                UsdGeom.XformCommonAPI(xform).SetTranslate((
                    origin_pos[0],
                    origin_pos[1],
                    new_trans
                    ))


        print("-" * 20, "Transform Sucessfully", "-" * 20)
