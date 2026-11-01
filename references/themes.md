# 公开版主题、角色与模板

默认 `theme=mint`、`mascot=block`，即薄荷绿小方块。三个角色都提供六套颜色及闭嘴/小口/大口三态，组合可独立选择。

| theme | 配色 | 默认角色 | 流程场景版式 |
| --- | --- | --- | --- |
| mint | 薄荷绿 | block 小方块 | 横向流程板 |
| coral | 珊瑚橙 | block 小方块 | 横向流程板 |
| honey | 蜂蜜黄 | bird 折纸鸟 | 分栏讲义 |
| berry | 莓果紫 | bird 折纸鸟 | 分栏讲义 |
| grape | 葡萄紫 | orbit 小轨道 | 深色路径图 |
| aqua | 荧光青 | orbit 小轨道 | 深色路径图 |

`new` 后，编辑**该期** `brand/style-lock.json` 的 `theme` 和 `mascot`，例如 `{"theme":"honey","mascot":"bird"}`。再继续语义分镜与批准、声音和assemble。现成episode.json也可设置顶层theme/mascot作技术预览，但正式版本应改本期品牌配置后重新assemble，避免配置不一致。不能覆盖其他人的项目或已经安装的Skill。

模板的差异由实际 Canvas 运行时执行：flow场景采用横排卡片、纵向分栏或路径节点。chapter、prompt-media、compare、note、ip-scene沿用其叙事用途并使用所选主题色。`ip-scene`不依赖预绘人物场景；默认几何角色配简洁内容板，也可以提供自己的background。仍支持1至4个流程步骤；更复杂内容按本期需要扩展。

主题色源是brand/themes.json，其运行时副本是runtime/themes.js；新增配色时须同时更新两者以及54个角色SVG的对应组合。角色资源在assets/mascots，不使用图片裁切或口部坐标补丁。停顿闭嘴，强调轻微上移/放大；嘴形仅由当期旁白包络驱动。

examples/public-templates仅为静音技术演示，使用合成包络展示嘴形，不能当作自然人声同步或新一期批准。
