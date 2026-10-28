# PuP DMD captures against the game's display effects

Written by `scripts/pup_captures.py` (23062 frames). D<n> fires in Visual Pinball when the pixels in the purple rectangle of `PupCapture/<n>.bmp` are on the DMD; *score* is the best frame's intersection over union of lit dots with it. *Effects*: every effect with a frame within 0.5 % of the best (2 % under 97 %). *Map*: the trigger map's events for D<n>; *by hand* when they carry conditions or are not display effect events (checked by hand, see the map's comments).

| D | rows | score | effects | map | |
|---|---|---|---|---|---|
| 1 | 2 | 100% | - | pup_attract_cycle | by hand |
| 2 | 3 328 329 330 367 | 100% | 25 | tf_deff_25 | ok |
| 3 | 4 335 337 338 340 341 343 352 | 100% | 38 | tf_deff_38 | ok |
| 4 | 5 354 | 100% | 1 | tf_deff_1 | ok |
| 5 | 6 | 100% | 42 | tf_deff_42{state.side==1} | by hand |
| 6 | 7 | 100% | 42 | tf_deff_42{state.side==2} | by hand |
| 7 | 8 | 100% | 43 | tf_deff_43 | ok |
| 8 | 9 | 100% | 20 | tf_deff_20 | ok |
| 9 | 10 12 397 | 100% | 21 | tf_deff_21 | ok |
| 10 | 249 253 254 256 258 265 332 366 | 96% | 40 | tf_deff_40{state.side==1} | by hand |
| 11 | 252 260 262 263 264 266 333 365 | 100% | 34 40 50 51 52 73 120 123 126 127 132 135 139 140 147 149 | tf_deff_40{state.side==2} | by hand |
| 12 | 14 267 269 271 272 345 | 52% | 41 | tf_deff_41{state.side==1} | by hand |
| 13 | 15 268 270 273 274 349 | 100% | 41 | tf_deff_41{state.side==2} | by hand |
| 14 | 17 | 58% | - | - | unused |
| 15 | 18 | 78% | - | - | unused |
| 16 | 19 358 | 100% | 129 | tf_deff_129 | ok |
| 17 | 21 | 100% | 126 | tf_deff_126 | unused |
| 18 | 22 | 40% | 66 72 78 | - | unused |
| 19 | 23 | 100% | 131 | tf_deff_131 | ok |
| 20 | 24 361 | 100% | 132 | tf_deff_132 | ok |
| 21 | 25 380 | 28% | 46 53 | tf_deff_137 | by hand |
| 22 | 28 306 307 359 | 100% | 100 | tf_deff_100 | ok |
| 23 | 29 | 100% | - | tf_deff_102{left==10} | by hand |
| 24 | - | 100% | 100 102 | tf_deff_102{left==9}<br>tf_deff_102{left==5} | unused |
| 25 | 31 | 100% | - | tf_deff_102{left==8} | by hand |
| 26 | 32 | 100% | - | tf_deff_102{left==7}<br>tf_deff_102{left==4} | by hand |
| 27 | 33 | 100% | - | tf_deff_102{left==6} | by hand |
| 28 | 34 | 100% | - | tf_deff_102{left==7}<br>tf_deff_102{left==4} | by hand |
| 29 | 35 | 100% | - | tf_deff_102{left==3} | by hand |
| 30 | 36 | 100% | - | tf_deff_102{left==2} | by hand |
| 31 | 37 | 100% | - | tf_deff_102{left==1} | by hand |
| 32 | 38 | 100% | - | tf_deff_102{completed==1} | by hand |
| 33 | 39 308 378 | 100% | 103 | tf_deff_103 | ok |
| 34 | 41 312 313 363 | 100% | 108 110 | tf_deff_108 | ok |
| 35 | 42 | 100% | - | tf_deff_110{left==5, completed==0} | by hand |
| 36 | 43 | 100% | - | tf_deff_110{left==4, completed==0} | by hand |
| 37 | 44 | 100% | - | tf_deff_110{left==3, completed==0} | by hand |
| 38 | 45 | 100% | - | tf_deff_110{left==2, completed==0} | by hand |
| 39 | 46 | 100% | - | tf_deff_110{left==1, completed==0} | by hand |
| 40 | 47 | 100% | - | tf_deff_110{left==0, completed==0} | by hand |
| 41 | 48 | 100% | - | tf_deff_110{completed==1} | by hand |
| 42 | 49 314 382 | 49% | 77 100 102 140 | tf_deff_111 | by hand |
| 43 | 51 296 298 348 | 100% | 104 106 | tf_deff_104 | ok |
| 44 | 53 | 100% | - | tf_deff_106{left==9} | by hand |
| 45 | 54 | 100% | - | tf_deff_106{left==8} | by hand |
| 46 | 55 | 100% | - | tf_deff_106{left==7} | by hand |
| 47 | 56 | 100% | - | tf_deff_106{left==6}<br>tf_deff_106{left==5} | by hand |
| 48 | 57 | 100% | - | tf_deff_106{left==4} | by hand |
| 49 | 58 | 100% | - | tf_deff_106{left==3} | by hand |
| 50 | 59 | 100% | - | tf_deff_106{left==2} | by hand |
| 51 | 60 | 100% | - | tf_deff_106{left==1} | by hand |
| 52 | 63 | 100% | - | tf_deff_106{completed==1} | by hand |
| 53 | 64 299 372 | 100% | 107 | tf_deff_107 | ok |
| 54 | 66 315 316 357 | 100% | 112 114 | tf_deff_112 | ok |
| 55 | 68 | 100% | - | tf_deff_114{left==9} | by hand |
| 56 | 69 | 100% | - | tf_deff_114{left==8} | by hand |
| 57 | 70 | 100% | - | tf_deff_114{left==7} | by hand |
| 58 | 71 | 100% | - | tf_deff_114{left==6} | by hand |
| 59 | 72 | 100% | - | tf_deff_114{left==5} | by hand |
| 60 | 73 | 100% | - | tf_deff_114{left==4} | by hand |
| 61 | 74 | 100% | - | tf_deff_114{left==3} | by hand |
| 62 | 75 | 100% | - | tf_deff_114{left==2} | by hand |
| 63 | 76 | 100% | - | tf_deff_114{left==1} | by hand |
| 64 | 77 | 100% | - | tf_deff_114{completed==1} | by hand |
| 65 | 78 317 377 | 100% | 115 | tf_deff_115 | ok |
| 66 | 80 318 319 350 | 100% | 116 | tf_deff_116 | ok |
| 67 | 81 | 100% | - | tf_deff_118{left==10} | by hand |
| 68 | 82 | 100% | - | tf_deff_118{left==9} | by hand |
| 69 | 83 | 100% | - | tf_deff_118{left==8} | by hand |
| 70 | 84 | 100% | - | tf_deff_118{left==7} | by hand |
| 71 | 85 | 100% | - | tf_deff_118{left==6} | by hand |
| 72 | 86 | 100% | - | tf_deff_118{left==5} | by hand |
| 73 | 87 | 100% | - | tf_deff_118{left==4} | by hand |
| 74 | 88 | 100% | - | tf_deff_118{left==3} | by hand |
| 75 | 89 | 100% | - | tf_deff_118{left==2} | by hand |
| 76 | 90 | 100% | - | tf_deff_118{left==1} | by hand |
| 77 | 91 | 100% | - | tf_deff_118{left==0} | by hand |
| 78 | 92 320 373 | 43% | - | tf_deff_119 | by hand |
| 79 | 94 321 322 355 | 100% | 120 122 | tf_deff_120 | ok |
| 80 | 95 | 100% | 57 61 68 69 73 75 89 91 100 101 102 103 108 110 112 113 114 115 | tf_deff_122{left==10} | by hand |
| 81 | 96 | 100% | - | tf_deff_122{left==1} | by hand |
| 82 | 97 | 100% | - | tf_deff_122{left==9} | by hand |
| 83 | 98 | 100% | - | tf_deff_122{left==8} | by hand |
| 84 | 99 | 100% | - | tf_deff_122{left==7} | by hand |
| 85 | 100 | 100% | - | tf_deff_122{left==6} | by hand |
| 86 | 101 | 100% | - | tf_deff_122{left==5} | by hand |
| 87 | 102 | 100% | - | tf_deff_122{left==4} | by hand |
| 88 | 103 | 100% | - | tf_deff_122{left==3} | by hand |
| 89 | 104 | 100% | - | tf_deff_122{left==2} | by hand |
| 90 | 105 | 100% | - | tf_deff_122{completed==1} | by hand |
| 91 | 106 323 375 | 100% | 123 | tf_deff_123 | ok |
| 92 | 109 309 310 360 | 100% | 98 | tf_deff_96 | by hand |
| 93 | 110 | 100% | - | tf_deff_98{left==10} | by hand |
| 94 | 111 | 100% | - | tf_deff_98{left==9} | by hand |
| 95 | 112 | 100% | - | tf_deff_98{left==8} | by hand |
| 96 | 113 | 99% | - | tf_deff_98{left==7} | by hand |
| 97 | 114 | 100% | - | tf_deff_98{left==6} | by hand |
| 98 | 115 | 100% | - | tf_deff_98{left==5} | by hand |
| 99 | 116 | 100% | - | tf_deff_98{left==4} | by hand |
| 100 | 117 | 100% | - | tf_deff_98{left==3} | by hand |
| 101 | 118 | 100% | - | tf_deff_98{left==2} | by hand |
| 102 | 119 | 100% | - | tf_deff_98{left==1} | by hand |
| 103 | 120 | 100% | - | tf_deff_98{completed==1} | by hand |
| 104 | 121 311 379 | 100% | 99 | tf_deff_99 | ok |
| 105 | 123 301 303 356 | 100% | 92 | tf_deff_92 | ok |
| 106 | 124 | 100% | - | tf_deff_94{left==9} | by hand |
| 107 | 125 | 100% | - | tf_deff_94{left==8} | by hand |
| 108 | 126 | 100% | - | tf_deff_94{left==7} | by hand |
| 109 | 127 | 100% | - | tf_deff_94{left==6} | by hand |
| 110 | 128 | 100% | - | tf_deff_94{left==5} | by hand |
| 111 | 129 | 100% | - | tf_deff_94{left==4} | by hand |
| 112 | 130 | 100% | - | tf_deff_94{left==3}<br>tf_deff_94{left==2}<br>tf_deff_94{left==1} | by hand |
| 113 | 131 | 100% | - | tf_deff_94{left==3}<br>tf_deff_94{left==2}<br>tf_deff_94{left==1} | by hand |
| 114 | 132 | 100% | - | tf_deff_94{completed==1} | by hand |
| 115 | 133 305 376 | 100% | 95 | tf_deff_95 | ok |
| 116 | 135 | 43% | 71 | - | unused |
| 117 | 136 | 44% | 28 29 75 100 102 116 | - | unused |
| 118 | 137 | 100% | 52 | tf_deff_52 | ok |
| 119 | 139 364 | 100% | - | tf_deff_142{state.side==1} | by hand |
| 120 | 140 | 100% | - | tf_deff_144{count==1, state.side==1} | by hand |
| 121 | 141 | 100% | - | tf_deff_144{count==2, state.side==1} | by hand |
| 122 | 142 | 100% | - | tf_deff_144{count==3, state.side==1} | by hand |
| 123 | 143 | 100% | - | tf_deff_144{count==4, state.side==1} | by hand |
| 124 | 144 | 100% | - | tf_deff_144{count==5, state.side==1} | by hand |
| 125 | 145 | 100% | - | tf_deff_144{count==6, state.side==1} | by hand |
| 126 | 146 | 100% | - | tf_deff_144{count==7, state.side==1} | by hand |
| 127 | 147 | 100% | - | tf_deff_144{count==8, state.side==1} | by hand |
| 128 | 148 287 290 351 | 100% | 57 | tf_deff_57 | ok |
| 129 | 151 | 100% | - | tf_deff_59{anim==1} | by hand |
| 130 | 152 | 100% | - | tf_deff_60{anim==1} | by hand |
| 131 | 154 | 100% | - | tf_deff_59{anim==3} | by hand |
| 132 | 155 | 100% | - | tf_deff_60{anim==3} | by hand |
| 133 | 156 | 100% | - | tf_deff_59{anim==4} | by hand |
| 134 | 157 | 100% | - | tf_deff_60{anim==4} | by hand |
| 135 | 158 | 100% | - | tf_deff_59{anim==5} | by hand |
| 136 | 159 | 100% | - | tf_deff_60{anim==5} | by hand |
| 137 | 160 | 100% | - | tf_deff_59{anim==0} | by hand |
| 138 | 161 | 100% | - | tf_deff_60{anim==0} | by hand |
| 139 | 162 | 100% | - | tf_deff_59{anim==2} | by hand |
| 140 | 163 | 100% | - | tf_deff_60{anim==2} | by hand |
| 141 | 164 | 100% | 61 | tf_deff_61 | ok |
| 142 | 169 362 | 100% | 142 | tf_deff_142{state.side==2} | by hand |
| 143 | 170 | 100% | - | tf_deff_144{count==1, state.side==2} | by hand |
| 144 | 171 | 100% | - | tf_deff_144{count==2, state.side==2} | by hand |
| 145 | 172 | 100% | - | tf_deff_144{count==3, state.side==2} | by hand |
| 146 | 173 | 100% | - | tf_deff_144{count==4, state.side==2} | by hand |
| 147 | 174 | 100% | - | tf_deff_144{count==5, state.side==2} | by hand |
| 148 | 175 | 100% | - | tf_deff_144{count==6, state.side==2} | by hand |
| 149 | 176 | 100% | - | tf_deff_144{count==7, state.side==2} | by hand |
| 150 | 177 | 100% | - | tf_deff_144{count==8, state.side==2} | by hand |
| 151 | 178 288 291 368 | 100% | 63 | tf_deff_63 | ok |
| 152 | 179 | 100% | 66 | tf_deff_66{anim==1} | by hand |
| 153 | 180 | 100% | - | tf_deff_66{anim==0} | by hand |
| 154 | 181 | 100% | - | tf_deff_66{anim==2} | by hand |
| 155 | 182 | 100% | 65 | tf_deff_65 | ok |
| 156 | 183 | 100% | 67 | tf_deff_67 | ok |
| 157 | 186 289 374 | 68% | 28 29 52 57 61 63 65 66 68 69 73 75 77 89 91 92 100 101 102 103 106 108 110 112 113 114 115 116 140 144 | tf_deff_62 | by hand |
| 158 | 188 | 100% | - | tf_deff_140{values.0==1, state.side==1} | by hand |
| 159 | 190 | 100% | - | tf_deff_140{values.0==2, state.side==1} | by hand |
| 160 | 191 | 100% | - | tf_deff_140{values.0==3, state.side==1} | by hand |
| 161 | 192 282 344 | 100% | 69 | tf_deff_69 | ok |
| 162 | 194 | 100% | - | tf_deff_71{anim==3} | by hand |
| 163 | 196 | 100% | - | tf_deff_71{anim==0} | by hand |
| 164 | 197 | 100% | - | tf_deff_71{anim==1} | by hand |
| 165 | 198 | 100% | - | tf_deff_72{anim==3} | by hand |
| 166 | 199 | 100% | 72 | tf_deff_72{anim==2} | by hand |
| 167 | 200 | 100% | - | tf_deff_72{anim==0} | by hand |
| 168 | 201 | 100% | - | tf_deff_72{anim==3} | by hand |
| 169 | 202 | 100% | 73 | tf_deff_73 | ok |
| 170 | 203 284 371 384 | 100% | 74 80 | tf_deff_74<br>tf_deff_80 | ok |
| 171 | 205 | 100% | - | tf_deff_140{values.0==1, state.side==2, state.mtl_music_d==663} | by hand |
| 172 | 206 | 100% | - | tf_deff_140{values.0==2, state.side==2, state.mtl_music_d==663} | by hand |
| 173 | 207 | 100% | 140 | tf_deff_140{values.0==3, state.side==2, state.mtl_music_d==663} | by hand |
| 174 | 208 | 100% | - | tf_deff_140{values.0==1, state.side==2, state.mtl_music_d==664}<br>tf_deff_140{values.0==1, state.side==2, state.mtl_music_d==665} | by hand |
| 175 | 209 | 100% | - | tf_deff_140{values.0==2, state.side==2, state.mtl_music_d==664}<br>tf_deff_140{values.0==2, state.side==2, state.mtl_music_d==665} | by hand |
| 176 | 210 | 100% | - | tf_deff_140{values.0==3, state.side==2, state.mtl_music_d==664}<br>tf_deff_140{values.0==3, state.side==2, state.mtl_music_d==665} | by hand |
| 177 | 211 283 347 | 100% | 75 | tf_deff_75 | ok |
| 178 | 214 | 100% | - | tf_deff_77{anim==8} | by hand |
| 179 | 215 | 100% | 77 | tf_deff_77{anim==0} | by hand |
| 180 | 216 | 100% | - | tf_deff_77{anim==2} | by hand |
| 181 | 217 | 100% | - | tf_deff_77{anim==3} | by hand |
| 182 | 218 | 100% | - | tf_deff_77{anim==6} | by hand |
| 183 | 219 | 100% | - | tf_deff_77{anim==4} | by hand |
| 184 | 220 | 100% | - | tf_deff_79 | by hand |
| 185 | 222 389 | 100% | - | tf_deff_81{state.side==1} | by hand |
| 186 | 223 | 39% | 28 29 67 84 87 89 98 108 110 | tf_deff_83{anim==11, state.side==1} | by hand |
| 187 | 224 | 61% | - | tf_deff_83{anim==10, state.side==1} | by hand |
| 188 | 225 | 42% | 28 29 75 86 87 89 98 | tf_deff_83{anim==9, state.side==1} | by hand |
| 189 | 226 | 47% | 75 | tf_deff_83{anim==8, state.side==1} | by hand |
| 190 | 227 | 50% | 25 | tf_deff_83{anim==6, state.side==1} | by hand |
| 191 | 228 | 41% | 28 29 52 61 65 66 72 75 84 89 92 98 108 110 112 114 | tf_deff_83{anim==7, state.side==1} | by hand |
| 192 | 229 | 99% | - | tf_deff_84{state.side==1} | by hand |
| 193 | 230 393 | 42% | 85 | tf_deff_85{state.side==1} | by hand |
| 194 | 231 388 | 100% | 81 | tf_deff_81{state.side==2} | by hand |
| 195 | 232 | 45% | 75 | tf_deff_83{anim==7, state.side==2} | by hand |
| 196 | 233 | 45% | 75 | tf_deff_83{anim==9, state.side==2} | by hand |
| 197 | 234 | 48% | - | tf_deff_83{anim==6, state.side==2} | by hand |
| 198 | 235 | 40% | 75 | tf_deff_83{anim==10, state.side==2} | by hand |
| 199 | 236 | 46% | 92 | tf_deff_83{anim==8, state.side==2} | by hand |
| 200 | 237 | 39% | 75 | tf_deff_83{anim==11, state.side==2} | by hand |
| 201 | 238 | 100% | 85 | tf_deff_84{state.side==2} | by hand |
| 202 | 239 392 | 100% | 85 | tf_deff_85{state.side==2} | by hand |
| 203 | 241 381 | 100% | 86 | tf_deff_86 | ok |
| 204 | - | 100% | 86 | - | unused |
| 205 | 243 | 100% | - | tf_deff_88{state.side==1} | by hand |
| 206 | 244 | 100% | - | tf_deff_89{state.side==1} | by hand |
| 207 | 383 | 100% | 90 | tf_deff_90 | ok |
| 208 | - | 65% | 42 61 140 | - | unused |
| 209 | 275 | 100% | - | tf_deff_77{anim==5} | by hand |
| 210 | 276 | 100% | - | tf_deff_77{anim==1} | by hand |
| 211 | 277 | 100% | - | tf_deff_77{anim==7} | by hand |
| 212 | 278 | 100% | 71 | tf_deff_71{anim==4} | by hand |
| 213 | 279 | 100% | - | tf_deff_72{anim==3} | by hand |
| 214 | 280 | 100% | - | tf_deff_72{anim==1} | by hand |
| 215 | 285 | 100% | 75 | tf_deff_75 | ok |
| 216 | 286 | 100% | 69 | tf_deff_69 | ok |
| 217 | - | 100% | 57 | - | unused |
| 218 | - | 100% | 63 | - | unused |
| 219 | 293 294 386 | 100% | 68 | tf_deff_68 | ok |
| 220 | - | 100% | 104 | - | unused |
| 221 | 325 | 100% | 54 | tf_deff_54 | ok |
| 222 | 326 | 100% | 26 | tf_deff_26 | ok |
| 223 | 395 | 39% | - | tf_deff_31 | by hand |
| 224 | 242 | 100% | - | tf_deff_88{state.side==2} | by hand |
| 225 | 245 | 100% | 89 | tf_deff_89{state.side==2} | by hand |
