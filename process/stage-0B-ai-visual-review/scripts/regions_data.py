# Agent pixel-review observations for Stage 0B (Claude viewed the labelled sheets in temp/stage0b/sheets).
# Names (P01 柚里 orange tee+glasses, P02 胤辰 white tee no glasses, P03 郁懷 black tee+black backpack) come from the
# user-confirmed list workspace/people/people_confirmed.json; matching here is by clothing/glasses only (medium confidence,
# no face recognition). Bystanders are 'unknown'.
P01 = dict(person_id="P01", name="柚里", evidence="橘色T恤+黑框紅鏡腳眼鏡", confidence="medium")
P02 = dict(person_id="P02", name="胤辰", evidence="白色T恤、短髮、無眼鏡", confidence="medium")
P03 = dict(person_id="P03", name="郁懷", evidence="黑色短袖+黑後背包+牛仔短褲+馬尾(僅背影)", confidence="low-medium")
U = lambda d: dict(person_id="unknown", name=None, evidence=d, confidence="n/a")
R = {}
def r(cid, **k): R[cid] = k

r("V001", summary="地鐵車廂內，白T恤小男孩側臉貼近車窗，窗玻璃映出他的臉；左側有穿粉色衣服的成人與手提包。鏡頭很貼近、微晃，後半(約1.5秒起)被髮絲與手臂遮住而變暗。",
  people=[dict(P02, note="只見側臉與反射，未見眼鏡")], animals=[], objects=["車窗反射","粉色衣物","手持紅色小物"], actions=["靠窗向外看"],
  env="地鐵車廂內，光線偏暗", reaction="安靜、專注", shot="close-up", roles=["person","reaction"], tone="cool-gray muted", light="low",
  anchor="小男孩側臉", cam="handheld, slight push/drift", dirn="unknown", motifs=[], cov="只有短暫的臉部，後半被遮蔽，動作不完整", conf=0.6, usable=0.6)
r("V002", summary="柚里(橘衣、戴眼鏡)趴在地鐵車窗邊的扶手上，頭微轉看窗外，後方是淺藍色座位與其他乘客；鏡頭在他身後/側面小幅晃動，畫面穩定偏暗。",
  people=[dict(P01, note="眼鏡紅色鏡腳清楚可見")], animals=[], objects=["車窗","淺藍色座椅","背包乘客"], actions=["趴在窗邊看窗外","微微轉頭"],
  env="地鐵車廂內", reaction="安靜、專注看窗外", shot="medium close-up", roles=["person","reaction","environment"], tone="muted teal and orange", light="low",
  anchor="柚里後腦與側臉", cam="handheld, slight sway", dirn="static", motifs=["橘色衣服對淺藍座椅"], cov="持續約15秒看窗外，無明顯事件", conf=0.8, usable=0.9)
r("V003", summary="自拍視角的柚里臉部特寫：手托腮、閉眼、吐舌，後半用手指推眼鏡並拿著粉色小玩偶，背景是地鐵車廂與躺臥的乘客；約1.8秒時被手臂/皮膚完全遮住鏡頭。",
  people=[dict(P01, note="臉部清楚、戴眼鏡")], animals=[], objects=["粉色小玩偶","黑框眼鏡","車廂座椅"], actions=["手托腮","吐舌","閉眼","用手指推眼鏡","拿玩偶"],
  env="地鐵車廂內", reaction="調皮、疲倦又好玩", shot="extreme close-up / selfie", roles=["person","reaction","hero_candidate"], tone="warm skin tones on gray-teal", light="low",
  anchor="柚里的臉", cam="handheld close, tilting", dirn="unknown", motifs=["紅色鏡腳"], cov="表情與動作連續約8秒，有一次完全遮擋(約1.8s)", conf=0.85, usable=0.85)
r("V004", summary="畫面上下顛倒：展場人群中，嬰兒推車裡有一隻灰色短毛貓(紅色項圈)，有人伸手摸牠；鏡頭靠近推車低處，約15秒時貓正對鏡頭。整體很暗。",
  people=[U("數名展場觀眾，只拍到手與衣服")], animals=[dict(label="灰色短毛貓(英短類)", confidence="medium", note="物種品種不確定")], objects=["嬰兒推車","紅色項圈","手提袋"], actions=["有人用手撫摸貓","鏡頭靠近觀察貓"],
  env="寵物展展場，人潮擁擠", reaction="貓安靜", shot="close-up", roles=["object","action","environment"], tone="dark gray with red accents", light="low",
  anchor="推車內的貓", cam="handheld, slow approach", dirn="unknown", motifs=["紅色項圈"], cov="貓持續可見；畫面倒置，需旋轉180度", conf=0.8, usable=0.6, flags=["frame_upside_down_rotation_metadata_0"])
r("V005", summary="展場人群中的低機位固定鏡頭：左側白T恤男子背對鏡頭、背帆布袋，右側灰衣戴口罩男子低頭，前景有戴口罩小孩側臉；背景為紅色攤位。",
  people=[U("白T恤男子(背影)、灰衣戴口罩男子、戴口罩兒童，皆非已確認人物")], animals=[], objects=["帆布袋","斜背包","紅色攤位招牌"], actions=["站著等候","人群駐足"],
  env="室內寵物展展場", reaction="unknown", shot="medium wide, low angle", roles=["environment"], tone="muted gray and red", light="medium",
  anchor="前景男子背部", cam="static handheld", dirn="static", motifs=[], cov="只有等待，沒有明確事件", conf=0.7, usable=0.8)
r("V006", summary="固定鏡頭拍一個貓咪造型立牌：白貓穿華服、牌子上寫「龍佑宮」，旁邊有三花貓；右側有人的背包肩帶入鏡，背景是紅色攤位。",
  people=[U("右側只見背包肩帶")], animals=[dict(label="貓(卡通插畫立牌)", confidence="high", note="非真貓")], objects=["龍佑宮 立牌","貓插畫"], actions=[],
  env="展場入口/攤位前", reaction="n/a", shot="medium static", roles=["object","creative","environment"], tone="red and teal, flat", light="medium",
  anchor="貓咪立牌", cam="locked-off", dirn="static", motifs=["紅色邊框","貓插畫"], cov="完整建立可讀招牌「龍佑宮」", conf=0.85, usable=0.9)
r("V007", summary="低機位跟拍展場：前景白T恤小孩(胤辰，手拿一張紙)側臉看向前方，前方穿黑衣背黑背包的女士(郁懷)走在前面，更前方有橘衣小孩。",
  people=[dict(P02, note="側臉，拿紙張"), dict(P03, note="背影"), dict(P01, note="遠處橘衣小孩背影，僅衣著吻合", confidence="low")], animals=[], objects=["紙張","黑色後背包","寵物用品攤位"], actions=["跟著走","看向前方"],
  env="寵物展展場", reaction="專注、好奇", shot="medium, child-height POV", roles=["person","environment","action"], tone="neutral gray", light="medium",
  anchor="胤辰側臉", cam="handheld following", dirn="forward", motifs=[], cov="跟走動作完整約5秒", conf=0.7, usable=0.85)
r("V008", summary="低機位跟著走在展場：郁懷(黑衣黑背包)牽著穿橘衣的小孩走過衣架攤位，前景是白T恤小孩的後腦與拿著白色雛菊氣球的手；約9.5秒地上出現一隻黑貓，旁邊有穿藍色洋裝的女士與其他攤位人員。",
  people=[dict(P03, note="牽手帶孩子"), dict(P01, note="橘衣小孩背影，無法確認臉部", confidence="low"), dict(P02, note="前景白衣小孩後腦")], animals=[dict(label="黑貓", confidence="medium", note="約9.5秒地面")], objects=["白色雛菊氣球","衣架上的黑白T恤","攤位招牌"], actions=["走過展場","牽手","拿氣球"],
  env="寵物展展場大廳，高天花板", reaction="好奇、愉快", shot="wide, low POV", roles=["environment","person","action"], tone="neutral with orange accent", light="medium",
  anchor="牽手的兩人背影", cam="handheld tracking forward", dirn="forward", motifs=["白色雛菊氣球","橘色衣服"], cov="行走過程完整；黑貓只出現在末段", conf=0.7, usable=0.85)
r("V009", summary="地鐵站出口階梯：先拍出入口指示牌與B1樓層圖，接著跟拍小孩下樓梯，最後柚里扶著扶手轉頭對鏡頭說話、低頭走下階梯，約14秒時快速擺動而模糊。",
  people=[dict(P01, note="臉部清楚，戴眼鏡"), dict(P02, note="階梯下方白衣小孩背影", confidence="low"), U("左側黑衣成人，無法辨識")], animals=[], objects=["不鏽鋼扶手","出口/B1指示牌","藍色牆面圖案(B1/B2)"], actions=["扶扶手下階梯","對鏡頭說話","轉頭"],
  env="地鐵站內出入口階梯", reaction="對鏡頭說話、轉頭看向前方", shot="medium close-up, handheld", roles=["person","action","environment","hero_candidate"], tone="cool gray and blue, dim", light="low",
  anchor="柚里面部/上半身", cam="handheld following", dirn="downward", motifs=["金屬扶手","藍色牆面"], cov="下樓過程與面對鏡頭互動完整；僅約14s動作模糊", conf=0.85, usable=0.85)
r("V010", summary="緩慢向右平移拍攝一個木架陳列：塑膠盒裝的魚、紅色與黃色小物整齊排列，牌子寫「100% 木天蓼填充」「小虱目魚 NT$150」「NT$180」「NT$380」。文字說明這是貓玩具而非食品。",
  people=[], animals=[], objects=["魚形貓玩具(盒裝)","價格牌 NT$150/180/380","木天蓼填充標示"], actions=["鏡頭平移掃視陳列"],
  env="寵物展攤位", reaction="n/a", shot="medium, pan", roles=["object","environment","creative"], tone="pale pastel on white", light="medium-high",
  anchor="價格牌與盒裝魚", cam="slow pan right", dirn="right", motifs=["盒裝魚形玩具","排列整齊的包裝"], cov="可讀文字：木天蓼、NT$150/180/380", conf=0.85, usable=0.9)
r("V011", summary="寬鏡頭拍展場的貓形照片牆裝置；鏡頭先橫掃牆面與出口標誌，約12秒起柚里(橘衣)與胤辰(白衣)在牆前的紫色舞台上拿著白色雛菊氣球跑跳、轉圈，約23秒柚里舉手。",
  people=[dict(P01, note="橘衣，距離遠，眼鏡不易辨識", confidence="low-medium"), dict(P02, note="白衣"), U("紅絲帶外戴口罩女士")], animals=[], objects=["貓形照片牆","白色雛菊氣球","紅色圍欄繩","展場出口標誌"], actions=["跑跳","揮舞氣球","舉手","圍著牆走"],
  env="室內展場，紫色舞台前", reaction="開心玩耍", shot="wide", roles=["action","person","environment","hero_candidate"], tone="lavender and white, soft", light="medium",
  anchor="貓形照片牆與前方玩耍的兩個孩子", cam="handheld slow pan then static", dirn="right", motifs=["白色雛菊氣球","貓耳形牆面"], cov="玩耍動作約16秒連續，人物偏小", conf=0.8, usable=0.9)
r("V012", summary="沿著暗色展牆走：牆上掛滿插畫畫作(樹、街景)，起頭有一張貓角色說明海報，鏡頭向前走入狹長展區。",
  people=[], animals=[dict(label="海報上的貓角色(插畫)", confidence="medium", note="非真貓")], objects=["框裱插畫","說明海報","QR code"], actions=["向前走看展"],
  env="室內藝術展區，暗色展牆", reaction="n/a", shot="medium moving", roles=["environment","object","creative"], tone="dark charcoal with muted green", light="low",
  anchor="牆上插畫", cam="handheld walking forward", dirn="forward", motifs=["框裱插畫列"], cov="可見海報部分文字，不足以判讀具體內容", conf=0.7, usable=0.75)
r("V013", summary="地鐵座位上柚里低頭用手機玩遊戲，耳機線垂下，旁邊坐著穿白底花朵圖案上衣的女士；固定鏡頭、車窗外有街景光影。",
  people=[dict(P01, note="戴眼鏡、低頭"), U("白色花朵T恤女士，已被使用者標為不追蹤(P04)")], animals=[], objects=["手機","耳機線","深藍色座椅","車窗"], actions=["低頭玩手機","手指滑動螢幕"],
  env="地鐵車廂內", reaction="專注", shot="medium, static", roles=["person","action"], tone="warm orange on dark blue", light="low-medium",
  anchor="柚里與手機", cam="static handheld", dirn="static", motifs=["橘衣對深藍座椅"], cov="整段專注玩手機", conf=0.9, usable=0.9)
r("V014", summary="低機位貼著白色檯面拍一排黑色圓筒罐，罐身寫「天然原肉」，印有貓圖案與「原味嫩雞丁」；鏡頭沿著罐子推進，焦點由前景罐移到背景牆上的商品。",
  people=[], animals=[dict(label="罐上的貓插圖", confidence="high", note="印刷圖案")], objects=["天然原肉罐頭","原味嫩雞丁","掛牆商品"], actions=["鏡頭沿檯面推進"],
  env="寵物展攤位", reaction="n/a", shot="low-angle close", roles=["object","creative"], tone="black and white, high contrast label", light="medium",
  anchor="罐身文字「天然原肉」", cam="handheld dolly-in with focus shift", dirn="forward", motifs=["重複排列的黑色圓罐"], cov="商品文字可讀", conf=0.85, usable=0.9)
r("V015", summary="約1秒的地鐵車廂短鏡頭：低角度拍淺藍色座椅與站著、坐著的乘客腳部，車窗在上方。",
  people=[U("數名乘客，腳部與背影")], animals=[], objects=["淺藍色座椅","吊環","車窗"], actions=["乘客站立"],
  env="地鐵車廂內", reaction="n/a", shot="wide low", roles=["environment"], tone="pale teal gray", light="low-medium",
  anchor="座椅與乘客", cam="static handheld", dirn="static", motifs=[], cov="僅1.1秒，抽樣1張", conf=0.7, usable=0.8)
r("V016", summary="展館大廳：白T恤小孩(胤辰)背著斜背小包、手拿折起的傳單，走向「Main Entrance」玻璃門，光滑地面有倒影，門外有行人。",
  people=[dict(P02, note="背影，斜背帶與傳單")], animals=[], objects=["Main Entrance 標示","玻璃自動門","服務台","傳單"], actions=["走向入口","跑向玻璃門"],
  env="展館入口大廳，室內明亮", reaction="n/a", shot="wide", roles=["person","action","environment"], tone="bright gray and orange accents", light="high",
  anchor="走向大門的小孩背影", cam="handheld following, wide", dirn="forward", motifs=["玻璃門倒影"], cov="接近出口全程", conf=0.85, usable=0.9)
r("V017", summary="戶外烈日下的石柱與不鏽鋼鏡面板之間：胤辰(白衣、斜背繩)背著手靠在鏡面板旁，抬頭、低頭、舉傳單遮陽，另一個小孩從畫面左側入鏡；畫面右側有金屬反射造成的朦朧遮蓋。",
  people=[dict(P02, note="臉部清楚"), U("左側另一個小孩，臉部不全")], animals=[], objects=["傳單(Taipei 字樣)","不鏽鋼鏡面板","石塊雕塑","高架軌道"], actions=["抬頭看","低頭","舉傳單遮陽","玩耍跑開"],
  env="戶外展館外廣場，晴天強光", reaction="開心、好奇", shot="close/medium close", roles=["person","action","reaction"], tone="washed bright", light="high",
  anchor="胤辰的臉", cam="handheld with slight handheld sway", dirn="static", motifs=["反射面板"], cov="互動約25秒，右側反射降低可用畫面", conf=0.75, usable=0.7, flags=["mirror_panel_veil_on_right"])
r("V018", summary="低機位鑽入灌木叢：枝幹間有黃黑警示帶，地面草地上有兩顆貌似蝸牛殼的物體，鏡頭逼近後焦點多次在枝幹與殼之間跳動，約12.5秒完全失焦。",
  people=[], animals=[dict(label="疑似蝸牛/螺類", confidence="low", note="外殼質感像蝸牛，但無法確認是否為活體或何種動物")], objects=["黃黑警示帶","樹幹","草地"], actions=["鏡頭靠近觀察地面物體"],
  env="戶外灌木林，地面苔蘚", reaction="n/a", shot="low close", roles=["object","environment"], tone="green and brown", light="medium",
  anchor="地面的殼", cam="handheld creeping forward, focus hunting", dirn="forward", motifs=["樹幹群"], cov="物種不確定，焦點失焦段落需略過", conf=0.55, usable=0.6, flags=["focus_hunting"])
r("V019", summary="長達2分鐘的低機位在灌木叢與樹幹間移動：開頭白色雛菊氣球入鏡、之後穿過密集樹幹，約33秒鏡頭朝下拍到一個人的腳(深色短褲、灰色運動鞋)走在人行道上，中段是人行道、地面落葉與影子，約65秒仰拍樹梢與玻璃頂棚並有一名深色衣著的成人在遠處，約101秒白色雛菊氣球與人影再次入鏡，約110秒激烈晃動模糊，結尾回到苔蘚地面，下方可見殼狀物體。口語指導如何用手機縮放錄影。",
  people=[U("只見腳部、影子與遠處深色衣著的成人，未見臉部，無法確認身分")], animals=[dict(label="疑似蝸牛/螺類", confidence="low", note="約117-131秒，下方殼狀物")], objects=["白色雛菊氣球","黃黑警示帶","樹幹群","落葉","人行道邊石","運動鞋與短褲(某人的腳)","玻璃頂棚"], actions=["低角度移動","氣球入鏡","搖晃"],
  env="戶外灌木叢與人行道，晴天", reaction="n/a", shot="low, wide-to-close", roles=["environment","creative"], tone="green with bright highlights", light="medium-high",
  anchor="樹幹群", cam="handheld wandering, strong shake near 110s", dirn="unknown", motifs=["重複的細樹幹","白色雛菊氣球"], cov="每6秒抽樣，涵蓋整段；多為相似的樹叢畫面", conf=0.6, usable=0.5, flags=["long_low_information","shake_at_110s"])
r("V020", summary="近2分40秒的戶外隨手拍：起頭遠處有橘衣小孩拿白色雛菊氣球走在石塊旁，之後鏡頭朝向高架橋、灌木、地面、牆面、玻璃建築與天空，中間有快速甩動、近乎全白的過曝天空、手臂特寫、「小心地滑」警示牌、禁菸標示的松鼠卡通立牌(約46秒)，多段天空近乎全白(約17、116秒)，結尾一名穿灰綠色POLO衫的成人走入畫面。",
  people=[dict(P01, note="開頭遠處橘衣小孩，僅衣著吻合", confidence="low"), U("結尾灰綠POLO衫成人，身分未知")], animals=[], objects=["白色雛菊氣球","小心地滑警示牌","禁菸標示的松鼠卡通立牌","高架橋","玻璃建築"], actions=["走路","甩動鏡頭","手臂入鏡"],
  env="戶外街道/廣場，晴天，強光", reaction="n/a", shot="mixed / unstable", roles=["environment"], tone="blown-out gray white", light="very high",
  anchor="無明顯主體", cam="handheld, whip pans, pointing at ground/sky", dirn="unknown", motifs=[], cov="每約6秒抽樣；大半是無主體畫面", conf=0.6, usable=0.3, flags=["long_low_information","overexposed_sky","strong_shake","whip_pans"])
r("V021", summary="地鐵月台安全門上的標示近拍：「小心月台間隙 Mind the platform gap」、關門時勿強行進出提示，下方有兩個播放箭頭符號與「9/7-13」海報，畫面偏暗且固定不動。",
  people=[], animals=[], objects=["月台安全門","小心月台間隙 標示","9/7-13 海報","箭頭符號"], actions=[],
  env="地鐵月台，暗", reaction="n/a", shot="close static", roles=["object","environment","creative"], tone="yellow signage on dark gray", light="low",
  anchor="月台間隙警示牌", cam="static", dirn="static", motifs=["黃色警示牌"], cov="標示文字清楚；僅2.5秒", conf=0.85, usable=0.8)
r("V022", summary="高架地鐵車頭窗前，胤辰(白衣)與柚里(橘衣、戴眼鏡)並排趴在窗邊看前方鐵軌與高樓；約3秒時胤辰回頭對鏡頭咧嘴笑，之後兩人持續望向前方，約45秒起可見前方高架車站，結尾(約52秒)列車駛入有頂棚的車站，兩人仍趴在窗邊看。畫面偏白、車窗朦朧。",
  people=[dict(P02, note="約3-4秒回頭笑，臉部清楚"), dict(P01, note="背影，26.6秒可見眼鏡鏡腳", confidence="medium")], animals=[], objects=["車頭窗","高架鐵軌","高樓","車站"], actions=["趴窗看前方","回頭對鏡頭笑","轉頭"],
  env="行駛中的高架地鐵車廂，白天", reaction="開心、期待", shot="medium wide, over-the-shoulder", roles=["person","reaction","environment","hero_candidate"], tone="soft pastel hazy", light="medium-high",
  anchor="兩個孩子的背影與前方軌道", cam="handheld, steady", dirn="forward", motifs=["兩個孩子並排的背影","向前延伸的鐵軌"], cov="約53秒，大部分為持續的望向前方畫面；高光區偏白", conf=0.9, usable=0.9, flags=["window_haze"])
r("V023", summary="暗色爬蟲/昆蟲展區：先拍玻璃箱內蕨葉下的甲蟲(疑似鍬形蟲/獨角仙類)，再平移掃過其他小玻璃箱，最後是木板與箱沿；整體偏暗、有玻璃反光。",
  people=[], animals=[dict(label="甲蟲(疑似鍬形蟲或獨角仙)", confidence="low", note="暗，細節不足")], objects=["玻璃飼養箱","蕨葉","椰纖/乾草","木板"], actions=["鏡頭平移看各箱"],
  env="寵物展爬蟲區，暗", reaction="n/a", shot="close then pan", roles=["object","environment"], tone="dark brown", light="low",
  anchor="箱內甲蟲", cam="handheld, slow pan", dirn="right", motifs=["玻璃箱"], cov="三種畫面：甲蟲、箱子、木板，物種不確定", conf=0.55, usable=0.6)
r("V024", summary="更暗的玻璃箱內：金屬網蓋與熱燈在上方，下方木頭與乾草上有一隻黑色昆蟲狀物體，鏡頭從網蓋向下移到木頭。",
  people=[], animals=[dict(label="黑色昆蟲(疑似甲蟲)", confidence="low", note="極暗")], objects=["金屬網蓋","木頭","乾草"], actions=["鏡頭由上往下移"],
  env="寵物展爬蟲區，非常暗", reaction="n/a", shot="close", roles=["object"], tone="very dark brown", light="very low",
  anchor="木頭上的黑色物體", cam="handheld tilt down", dirn="down", motifs=[], cov="畫質差，主體不易辨", conf=0.45, usable=0.4, flags=["very_dark"])
r("V025", summary="暗色岩壁造景的玻璃箱：一根橫木與斜放的石板，右側有玻璃邊框；石板上中央隱約有一個灰色小形體，無法確認是否為動物。",
  people=[], animals=[dict(label="不確定(可能有小型爬蟲)", confidence="unknown", note="石板上有灰色小形體")], objects=["岩壁造景","橫木","石板","玻璃邊框"], actions=[],
  env="寵物展爬蟲區，暗", reaction="n/a", shot="medium static", roles=["environment","object"], tone="dark blue-gray", light="very low",
  anchor="石板上的小形體", cam="static", dirn="static", motifs=[], cov="僅2.4秒，主體不確定", conf=0.4, usable=0.4, flags=["very_dark","subject_unclear"])
r("V026", summary="玻璃箱內的綠鬣蜥(淡藍灰色個體)趴在木製斜坡上休息，長尾巴橫過畫面下方，背景是石壁；固定鏡頭，色調偏灰。",
  people=[], animals=[dict(label="鬣蜥(疑似綠鬣蜥)", confidence="medium", note="體色偏淡，屬不確定")], objects=["木製斜坡","石壁","玻璃箱"], actions=["趴著休息"],
  env="寵物展爬蟲區", reaction="n/a", shot="medium static", roles=["object","environment"], tone="gray-blue pastel", light="low-medium",
  anchor="鬣蜥頭部", cam="static", dirn="static", motifs=["帶斑紋的長尾"], cov="可辨識主體，動作很少", conf=0.7, usable=0.8)
r("V027", summary="很暗的玻璃上貼著一隻壁虎(從腹面看到腳趾吸盤)，背景為黑色植物與玻璃反射的人影；畫面幾乎全黑，細節弱。",
  people=[U("右側玻璃反射的人影")], animals=[dict(label="壁虎類", confidence="medium", note="可見趾墊，種類未知")], objects=["玻璃","木框","植物"], actions=["壁虎貼在玻璃上"],
  env="寵物展爬蟲區，極暗", reaction="n/a", shot="close static", roles=["object"], tone="near black", light="very low",
  anchor="壁虎", cam="static", dirn="static", motifs=[], cov="極暗；可辨識主體輪廓", conf=0.55, usable=0.45, flags=["very_dark"])
r("V028", summary="熱燈照射下的岩石上並排兩隻淡黃色鬃獅蜥(又稱肥尾/鬍鬚龍類)，其中一隻抬頭向前、另一隻趴著，固定鏡頭，背景玻璃有細微反光。",
  people=[], animals=[dict(label="鬃獅蜥(疑似)", confidence="medium", note="兩隻")], objects=["岩石","熱燈","玻璃箱"], actions=["趴著、抬頭"],
  env="寵物展爬蟲區", reaction="n/a", shot="medium static", roles=["object","environment"], tone="warm beige on dark", light="low",
  anchor="兩隻蜥蜴", cam="static", dirn="static", motifs=["岩石上的並列蜥蜴"], cov="兩隻皆可見", conf=0.7, usable=0.8)
r("V029", summary="鬃獅蜥特寫：一隻抬頭挺胸站在岩石上，喉部皮膚與紋理清楚，另一隻在左下角貼著岩石趴著，鏡頭輕微前後移動。",
  people=[], animals=[dict(label="鬃獅蜥(疑似)", confidence="medium", note="兩隻")], objects=["岩石","玻璃箱"], actions=["抬頭站立","趴著休息"],
  env="寵物展爬蟲區", reaction="n/a", shot="close-up", roles=["object","creative"], tone="warm cream, soft contrast", light="low-medium",
  anchor="抬頭蜥蜴的頭部", cam="handheld slight movement", dirn="static", motifs=["蜥蜴側臉"], cov="動物細節佳，事件性不足", conf=0.8, usable=0.85)
r("V030", summary="昏暗水箱內，一隻體型厚重的大型龜(疑似鱷龜或類似淡水龜)把頭靠在石頭上，頭部與前腳指甲慢慢移動，背景上方有藍色標牌；畫面很暗。",
  people=[], animals=[dict(label="大型淡水龜(疑似鱷龜)", confidence="low", note="暗，種類不確定")], objects=["水箱","石頭","藍色標牌"], actions=["緩慢抬頭、前腳動"],
  env="寵物展爬蟲/水族區，暗", reaction="n/a", shot="close static", roles=["object"], tone="dark green-brown", light="very low",
  anchor="龜頭", cam="static", dirn="static", motifs=[], cov="主體可辨，細節因暗度不足", conf=0.5, usable=0.5, flags=["very_dark"])
r("V031", summary="極暗：畫面中有綠色葉片、樹枝與棕色纖維壁，上方隱約有一個深色形體(可能是樹蛙或其他小動物)，下方有白色小物體入鏡；難以判讀。",
  people=[], animals=[dict(label="不確定(可能有小型動物)", confidence="unknown", note="上方深色形體")], objects=["葉片","樹枝","棕色纖維壁"], actions=[],
  env="寵物展爬蟲區，幾乎全黑", reaction="n/a", shot="close static", roles=["object"], tone="near black green", light="very low",
  anchor="葉片與枝條", cam="static handheld", dirn="static", motifs=[], cov="主體不明，記為 uncertain", conf=0.3, usable=0.3, flags=["very_dark","subject_unclear"])
r("V032", summary="明亮一些的玻璃箱：一隻鬃獅蜥貼在左側，頭抬起；約3秒起右側有一根金屬夾/管入鏡靠近蜥蜴，旁邊有大石塊與沙土地。",
  people=[], animals=[dict(label="鬃獅蜥(疑似)", confidence="medium", note="一隻")], objects=["金屬夾或金屬管","石塊","沙土"], actions=["金屬物體靠近蜥蜴","蜥蜴抬頭"],
  env="寵物展爬蟲區", reaction="n/a", shot="medium static", roles=["object","action"], tone="warm sand gray", light="medium",
  anchor="蜥蜴與入鏡的金屬物", cam="static", dirn="static", motifs=[], cov="金屬物體用途不明(可能為夾子/餵食工具)，不下結論", conf=0.65, usable=0.8)
r("V033", summary="暗色玻璃箱內：一根直立的樹枝上掛著枝葉，下方有蕨葉，上方有一盞小燈；枝條上有疑似變色龍或壁虎的形體(左側)，非常暗。",
  people=[], animals=[dict(label="不確定(疑似變色龍/壁虎)", confidence="low", note="枝條上的形體")], objects=["樹枝","蕨葉","燈"], actions=[],
  env="寵物展爬蟲區，暗", reaction="n/a", shot="medium static", roles=["object","environment"], tone="near black green", light="very low",
  anchor="樹枝上的形體", cam="static", dirn="static", motifs=[], cov="主體不易辨", conf=0.4, usable=0.45, flags=["very_dark"])
r("V034", summary="不到半秒的暗色玻璃箱：一盞熱燈、箱底有餵食盤與餐具狀的容器；只有一張畫面可辨。",
  people=[], animals=[], objects=["熱燈","飼料盤","玻璃箱"], actions=[],
  env="寵物展爬蟲區，暗", reaction="n/a", shot="wide static", roles=["environment"], tone="near black", light="very low",
  anchor="熱燈", cam="static", dirn="static", motifs=[], cov="僅0.45秒，抽樣1張", conf=0.4, usable=0.3, flags=["very_dark","very_short"])
r("V035", summary="箱內三隻陸龜：左後方有大型淡色龜與一隻小龜，前方一隻深色花紋陸龜朝鏡頭慢慢走近，頭部抬起，腳下有碎石片與木屑。",
  people=[], animals=[dict(label="陸龜(疑似希臘陸龜/赫曼陸龜類)", confidence="low-medium", note="種類不確定，共三隻")], objects=["石片","木屑","玻璃箱"], actions=["陸龜走向鏡頭","抬頭"],
  env="寵物展爬蟲區，暖光", reaction="n/a", shot="medium close", roles=["object","action","hero_candidate"], tone="warm tan", light="medium",
  anchor="前景陸龜", cam="static handheld", dirn="toward camera", motifs=["龜殼花紋"], cov="約10秒連續動作", conf=0.8, usable=0.9)
