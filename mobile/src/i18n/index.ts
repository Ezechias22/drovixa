import { getLocales } from 'expo-localization';
import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';

export type LanguageCode = 'ht' | 'fr' | 'pt-BR' | 'es' | 'en';

export const languages: Array<{ code: LanguageCode; label: string; nativeLabel: string }> = [
  { code: 'ht', label: 'Haitian Creole', nativeLabel: 'Kreyòl ayisyen' },
  { code: 'fr', label: 'French', nativeLabel: 'Français' },
  { code: 'pt-BR', label: 'Portuguese', nativeLabel: 'Português (Brasil)' },
  { code: 'es', label: 'Spanish', nativeLabel: 'Español' },
  { code: 'en', label: 'English', nativeLabel: 'English' },
];

const translations = {
  en: {
    'nav.home': 'Home', 'nav.discover': 'Discover', 'nav.shorts': 'Shorts', 'nav.library': 'My List', 'nav.profile': 'Profile',
    'common.loading': 'Loading…', 'common.retry': 'Try again', 'common.errorTitle': 'Something went wrong', 'common.errorBody': 'Check your connection and try again.', 'common.signIn': 'Sign in', 'common.cancel': 'Cancel', 'common.delete': 'Delete',
    'home.featured': 'FEATURED', 'home.original': 'DROVIXA ORIGINAL', 'home.watch': 'Watch now', 'home.more': 'More info', 'home.emptyTitle': 'Catalog connected', 'home.emptyBody': 'Published content will appear here automatically.',
    'discover.eyebrow': 'FIND YOUR NEXT OBSESSION', 'discover.search': 'Series, movies, actors…', 'discover.all': 'All moods', 'discover.popular': 'Popular', 'discover.new': 'New', 'discover.rating': 'Rating', 'discover.emptyTitle': 'Nothing found', 'discover.emptyBody': 'Try another genre.',
    'library.eyebrow': 'YOUR SPACE', 'library.title': 'My List', 'library.guestTitle': 'Keep every story close', 'library.guestBody': 'Sign in to sync saved series and movies across your devices.', 'library.emptyTitle': 'Your list is empty', 'library.emptyBody': 'Save a series or movie and it will appear here.',
    'profile.eyebrow': 'ACCOUNT', 'profile.title': 'Profile', 'profile.guest': 'Guest mode', 'profile.guestBody': 'Sign in to unlock your personalized Drovixa experience.', 'profile.createAccount': 'Create account', 'profile.signOut': 'Sign out', 'profile.signingOut': 'Signing out…',
    'profile.profiles': 'Profiles', 'profile.premium': 'Premium', 'profile.coins': 'Coins', 'profile.rewards': 'Rewards & referrals', 'profile.myList': 'My List', 'profile.downloads': 'Downloads', 'profile.notifications': 'Notifications', 'profile.language': 'Language', 'profile.subtitles': 'Subtitle settings', 'profile.playback': 'Playback', 'profile.devices': 'Devices', 'profile.security': 'Security', 'profile.help': 'Help Center',
    'language.title': 'Language', 'language.subtitle': 'Choose the language used throughout Drovixa.', 'language.device': 'Drovixa follows your phone language until you choose one.',
    'playback.title': 'Playback', 'playback.subtitle': 'Control how videos start on this device.', 'playback.autoplay': 'Autoplay videos', 'playback.autoplayBody': 'Start playback automatically after secure authorization.',
    'help.title': 'Help Center', 'help.subtitle': 'Quick answers and direct support when you need it.', 'help.search': 'Search help', 'help.contact': 'Contact support', 'help.email': 'Email Drovixa support', 'help.faq1q': 'Why will a video not play?', 'help.faq1a': 'Check your connection, then tap Retry playback. If the issue continues, send support the error shown on screen.', 'help.faq2q': 'How do downloads work?', 'help.faq2a': 'Premium members can save eligible videos. Drovixa prepares the offline copy, downloads it to private app storage and checks its license.', 'help.faq3q': 'How do I change language?', 'help.faq3a': 'Open Profile, choose Language, then select one of the five available languages.',
    'security.title': 'Security', 'security.subtitle': 'Protect your account and review where it is signed in.', 'security.devices': 'Review signed-in devices', 'security.logoutAll': 'Sign out all devices', 'security.logoutConfirm': 'Sign out everywhere?', 'security.logoutBody': 'Every Drovixa session, including this phone, will be closed.', 'security.done': 'All sessions were closed.', 'security.password': 'Change password', 'security.current': 'Current password', 'security.new': 'New password', 'security.confirm': 'Confirm new password', 'security.update': 'Update password', 'security.updated': 'Password updated successfully.',
    'notifications.guestTitle': 'Stay in the story', 'notifications.guestBody': 'Sign in for new episode, account and security notifications.', 'notifications.emptyTitle': 'No notifications', 'notifications.emptyBody': 'Updates from Drovixa will appear here.',
    'downloads.eyebrow': 'OFFLINE & PRIVATE', 'downloads.title': 'Downloads', 'downloads.subtitle': "Videos stay inside Drovixa's private app storage and stop playing when their license expires.", 'downloads.emptyTitle': 'No downloads yet', 'downloads.emptyBody': 'Use Download from a movie or episode player.', 'downloads.expired': 'LICENSE EXPIRED', 'downloads.validUntil': 'VALID UNTIL {date}', 'downloads.deleteTitle': 'Delete download?',
    'player.authorizing': 'Authorizing secure playback…', 'player.unavailable': 'Playback unavailable', 'player.tryLater': 'Please try again later.', 'player.failed': 'Video playback failed.', 'player.refresh': 'Refresh the secure playback link and try again.', 'player.retry': 'Retry playback', 'player.pause': 'Pause', 'player.play': 'Play', 'player.download': 'Download', 'player.preparing': 'Preparing', 'player.downloading': 'Downloading', 'player.saving': 'Saving', 'player.readyTitle': 'Download ready', 'player.readyBody': 'The video is saved in Drovixa private storage.',
    'search.placeholder': 'Series, movies, actors, genres…', 'search.trending': 'Trending searches', 'search.searching': 'Searching…', 'search.emptyTitle': 'No results', 'search.emptyBody': 'Try a different title, actor, genre or keyword.',
    'content.play': 'Play', 'content.saved': 'Saved', 'content.myList': 'My List', 'content.genres': 'Genres', 'content.cast': 'Cast', 'content.episodes': 'Episodes', 'content.noEpisodes': 'No episodes yet', 'content.noEpisodesBody': 'Published episodes will appear here.', 'content.movie': 'Movie', 'content.episodeCount': '{count} episodes',
    'devices.title': 'Your devices', 'devices.subtitle': 'Review every signed-in device and revoke sessions you do not recognize.', 'devices.current': 'CURRENT DEVICE', 'devices.remove': 'Remove', 'devices.confirm': 'Sign out device?',
  },
  ht: {
    'nav.home': 'Akèy', 'nav.discover': 'Dekouvri', 'nav.shorts': 'Kout videyo', 'nav.library': 'Lis mwen', 'nav.profile': 'Pwofil',
    'common.loading': 'Ap chaje…', 'common.retry': 'Eseye ankò', 'common.errorTitle': 'Gen yon pwoblèm', 'common.errorBody': 'Verifye koneksyon ou epi eseye ankò.', 'common.signIn': 'Konekte', 'common.cancel': 'Anile', 'common.delete': 'Efase',
    'home.featured': 'AN VEDET', 'home.original': 'YON ORIJINAL DROVIXA', 'home.watch': 'Gade kounye a', 'home.more': 'Plis detay', 'home.emptyTitle': 'Katalòg la konekte', 'home.emptyBody': 'Kontni ki pibliye yo ap parèt isit la otomatikman.',
    'discover.eyebrow': 'JWENN PWOCHEN ISTWA OU', 'discover.search': 'Seri, fim, aktè…', 'discover.all': 'Tout estil', 'discover.popular': 'Popilè', 'discover.new': 'Nouvo', 'discover.rating': 'Nòt', 'discover.emptyTitle': 'Pa gen rezilta', 'discover.emptyBody': 'Eseye yon lòt jan.',
    'library.eyebrow': 'ESPAS OU', 'library.title': 'Lis mwen', 'library.guestTitle': 'Kenbe tout istwa ou yo pre', 'library.guestBody': 'Konekte pou senkronize seri ak fim ou sove sou tout aparèy ou.', 'library.emptyTitle': 'Lis ou vid', 'library.emptyBody': 'Sove yon seri oswa yon fim epi l ap parèt isit la.',
    'profile.eyebrow': 'KONT', 'profile.title': 'Pwofil', 'profile.guest': 'Mòd envite', 'profile.guestBody': 'Konekte pou jwenn eksperyans Drovixa ki adapte pou ou.', 'profile.createAccount': 'Kreye kont', 'profile.signOut': 'Dekonekte', 'profile.signingOut': 'Ap dekonekte…',
    'profile.profiles': 'Pwofil yo', 'profile.premium': 'Premium', 'profile.coins': 'Pyès', 'profile.rewards': 'Rekonpans ak referans', 'profile.myList': 'Lis mwen', 'profile.downloads': 'Telechajman', 'profile.notifications': 'Notifikasyon', 'profile.language': 'Lang', 'profile.subtitles': 'Paramèt soutit', 'profile.playback': 'Lekti videyo', 'profile.devices': 'Aparèy', 'profile.security': 'Sekirite', 'profile.help': 'Sant èd',
    'language.title': 'Lang', 'language.subtitle': 'Chwazi lang Drovixa dwe itilize toupatou.', 'language.device': 'Drovixa suiv lang telefòn ou jiskaske ou chwazi youn.',
    'playback.title': 'Lekti videyo', 'playback.subtitle': 'Kontwole kijan videyo yo demare sou aparèy sa a.', 'playback.autoplay': 'Jwe videyo otomatikman', 'playback.autoplayBody': 'Demare videyo a otomatikman apre otorizasyon sekirize a.',
    'help.title': 'Sant èd', 'help.subtitle': 'Repons rapid ak sipò dirèk lè ou bezwen li.', 'help.search': 'Chèche èd', 'help.contact': 'Kontakte sipò', 'help.email': 'Voye imèl bay sipò Drovixa', 'help.faq1q': 'Poukisa yon videyo pa jwe?', 'help.faq1a': 'Verifye koneksyon ou, epi peze Eseye playback ankò. Si sa kontinye, voye erè ki sou ekran an bay sipò.', 'help.faq2q': 'Kijan telechajman fonksyone?', 'help.faq2a': 'Manm Premium ka sove videyo ki elijib. Drovixa prepare kopi offline lan, mete li nan espas prive app la epi verifye lisans li.', 'help.faq3q': 'Kijan pou mwen chanje lang?', 'help.faq3a': 'Louvri Pwofil, chwazi Lang, epi chwazi youn nan senk lang yo.',
    'security.title': 'Sekirite', 'security.subtitle': 'Pwoteje kont ou epi verifye ki kote li konekte.', 'security.devices': 'Verifye aparèy ki konekte yo', 'security.logoutAll': 'Dekonekte tout aparèy', 'security.logoutConfirm': 'Dekonekte tout kote?', 'security.logoutBody': 'Tout sesyon Drovixa yo, menm telefòn sa a, ap fèmen.', 'security.done': 'Tout sesyon yo fèmen.', 'security.password': 'Chanje modpas', 'security.current': 'Modpas aktyèl', 'security.new': 'Nouvo modpas', 'security.confirm': 'Konfime nouvo modpas', 'security.update': 'Mete modpas ajou', 'security.updated': 'Modpas la chanje avèk siksè.',
    'notifications.guestTitle': 'Rete branche ak istwa yo', 'notifications.guestBody': 'Konekte pou resevwa nouvo epizòd, enfòmasyon kont ak alèt sekirite.', 'notifications.emptyTitle': 'Pa gen notifikasyon', 'notifications.emptyBody': 'Nouvèl Drovixa yo ap parèt isit la.',
    'downloads.eyebrow': 'OFFLINE AK PRIVE', 'downloads.title': 'Telechajman', 'downloads.subtitle': 'Videyo yo rete nan espas prive Drovixa epi yo sispann jwe lè lisans yo ekspire.', 'downloads.emptyTitle': 'Poko gen telechajman', 'downloads.emptyBody': 'Sèvi ak Telechaje nan player yon fim oswa epizòd.', 'downloads.expired': 'LISANS EKSPIRE', 'downloads.validUntil': 'VALID JISKA {date}', 'downloads.deleteTitle': 'Efase telechajman an?',
    'player.authorizing': 'N ap otorize playback sekirize a…', 'player.unavailable': 'Playback pa disponib', 'player.tryLater': 'Tanpri eseye ankò pita.', 'player.failed': 'Videyo a pa rive jwe.', 'player.refresh': 'Renouvle lyen sekirize a epi eseye ankò.', 'player.retry': 'Eseye playback ankò', 'player.pause': 'Poz', 'player.play': 'Jwe', 'player.download': 'Telechaje', 'player.preparing': 'N ap prepare', 'player.downloading': 'N ap telechaje', 'player.saving': 'N ap sove', 'player.readyTitle': 'Telechajman pare', 'player.readyBody': 'Videyo a sove nan espas prive Drovixa.',
    'search.placeholder': 'Seri, fim, aktè, jan…', 'search.trending': 'Rechèch popilè', 'search.searching': 'N ap chèche…', 'search.emptyTitle': 'Pa gen rezilta', 'search.emptyBody': 'Eseye yon lòt tit, aktè, jan oswa mo.',
    'content.play': 'Jwe', 'content.saved': 'Sove', 'content.myList': 'Lis mwen', 'content.genres': 'Jan', 'content.cast': 'Aktè', 'content.episodes': 'Epizòd', 'content.noEpisodes': 'Poko gen epizòd', 'content.noEpisodesBody': 'Epizòd ki pibliye yo ap parèt isit la.', 'content.movie': 'Fim', 'content.episodeCount': '{count} epizòd',
    'devices.title': 'Aparèy ou yo', 'devices.subtitle': 'Verifye tout aparèy ki konekte epi retire sa ou pa rekonèt yo.', 'devices.current': 'APARÈY AKTYÈL', 'devices.remove': 'Retire', 'devices.confirm': 'Dekonekte aparèy la?',
  },
  fr: {
    'nav.home': 'Accueil', 'nav.discover': 'Découvrir', 'nav.shorts': 'Vidéos courtes', 'nav.library': 'Ma liste', 'nav.profile': 'Profil',
    'common.loading': 'Chargement…', 'common.retry': 'Réessayer', 'common.errorTitle': 'Un problème est survenu', 'common.errorBody': 'Vérifiez votre connexion et réessayez.', 'common.signIn': 'Se connecter', 'common.cancel': 'Annuler', 'common.delete': 'Supprimer',
    'home.featured': 'À LA UNE', 'home.original': 'UNE CRÉATION DROVIXA', 'home.watch': 'Regarder', 'home.more': "Plus d'infos", 'home.emptyTitle': 'Catalogue connecté', 'home.emptyBody': 'Le contenu publié apparaîtra ici automatiquement.',
    'discover.eyebrow': 'TROUVEZ VOTRE PROCHAINE PASSION', 'discover.search': 'Séries, films, acteurs…', 'discover.all': 'Toutes les ambiances', 'discover.popular': 'Populaires', 'discover.new': 'Nouveautés', 'discover.rating': 'Note', 'discover.emptyTitle': 'Aucun résultat', 'discover.emptyBody': 'Essayez un autre genre.',
    'library.eyebrow': 'VOTRE ESPACE', 'library.title': 'Ma liste', 'library.guestTitle': 'Gardez toutes vos histoires à portée de main', 'library.guestBody': 'Connectez-vous pour synchroniser vos séries et films sur tous vos appareils.', 'library.emptyTitle': 'Votre liste est vide', 'library.emptyBody': 'Enregistrez une série ou un film pour le retrouver ici.',
    'profile.eyebrow': 'COMPTE', 'profile.title': 'Profil', 'profile.guest': 'Mode invité', 'profile.guestBody': 'Connectez-vous pour profiter de votre expérience Drovixa personnalisée.', 'profile.createAccount': 'Créer un compte', 'profile.signOut': 'Se déconnecter', 'profile.signingOut': 'Déconnexion…',
    'profile.profiles': 'Profils', 'profile.premium': 'Premium', 'profile.coins': 'Pièces', 'profile.rewards': 'Récompenses et parrainages', 'profile.myList': 'Ma liste', 'profile.downloads': 'Téléchargements', 'profile.notifications': 'Notifications', 'profile.language': 'Langue', 'profile.subtitles': 'Paramètres des sous-titres', 'profile.playback': 'Lecture', 'profile.devices': 'Appareils', 'profile.security': 'Sécurité', 'profile.help': "Centre d'aide",
    'language.title': 'Langue', 'language.subtitle': 'Choisissez la langue utilisée dans Drovixa.', 'language.device': 'Drovixa suit la langue du téléphone jusqu’à votre choix.',
    'playback.title': 'Lecture', 'playback.subtitle': 'Contrôlez le démarrage des vidéos sur cet appareil.', 'playback.autoplay': 'Lecture automatique', 'playback.autoplayBody': 'Démarrer la vidéo après son autorisation sécurisée.',
    'help.title': "Centre d'aide", 'help.subtitle': 'Des réponses rapides et une assistance directe.', 'help.search': "Rechercher dans l'aide", 'help.contact': "Contacter l'assistance", 'help.email': "Envoyer un e-mail à Drovixa", 'help.faq1q': 'Pourquoi une vidéo ne se lance-t-elle pas ?', 'help.faq1a': "Vérifiez votre connexion, puis appuyez sur Réessayer. Si le problème persiste, envoyez à l'assistance l'erreur affichée.", 'help.faq2q': 'Comment fonctionnent les téléchargements ?', 'help.faq2a': "Les membres Premium peuvent enregistrer les vidéos éligibles. Drovixa prépare la copie hors ligne, la télécharge dans l'espace privé et vérifie sa licence.", 'help.faq3q': 'Comment changer de langue ?', 'help.faq3a': 'Ouvrez Profil, choisissez Langue, puis sélectionnez une des cinq langues.',
    'security.title': 'Sécurité', 'security.subtitle': 'Protégez votre compte et contrôlez ses connexions.', 'security.devices': 'Voir les appareils connectés', 'security.logoutAll': 'Déconnecter tous les appareils', 'security.logoutConfirm': 'Se déconnecter partout ?', 'security.logoutBody': 'Toutes les sessions Drovixa, y compris ce téléphone, seront fermées.', 'security.done': 'Toutes les sessions ont été fermées.', 'security.password': 'Modifier le mot de passe', 'security.current': 'Mot de passe actuel', 'security.new': 'Nouveau mot de passe', 'security.confirm': 'Confirmer le nouveau mot de passe', 'security.update': 'Mettre à jour le mot de passe', 'security.updated': 'Mot de passe mis à jour.',
    'notifications.guestTitle': 'Restez dans l’histoire', 'notifications.guestBody': 'Connectez-vous pour recevoir les nouveautés et les alertes de sécurité.', 'notifications.emptyTitle': 'Aucune notification', 'notifications.emptyBody': 'Les actualités Drovixa apparaîtront ici.',
    'downloads.eyebrow': 'HORS LIGNE ET PRIVÉ', 'downloads.title': 'Téléchargements', 'downloads.subtitle': "Les vidéos restent dans l'espace privé de Drovixa et expirent avec leur licence.", 'downloads.emptyTitle': 'Aucun téléchargement', 'downloads.emptyBody': "Utilisez Télécharger depuis le lecteur d'un film ou épisode.", 'downloads.expired': 'LICENCE EXPIRÉE', 'downloads.validUntil': "VALABLE JUSQU'AU {date}", 'downloads.deleteTitle': 'Supprimer le téléchargement ?',
    'player.authorizing': 'Autorisation de la lecture sécurisée…', 'player.unavailable': 'Lecture indisponible', 'player.tryLater': 'Veuillez réessayer plus tard.', 'player.failed': 'La lecture de la vidéo a échoué.', 'player.refresh': 'Actualisez le lien sécurisé et réessayez.', 'player.retry': 'Réessayer la lecture', 'player.pause': 'Pause', 'player.play': 'Lire', 'player.download': 'Télécharger', 'player.preparing': 'Préparation', 'player.downloading': 'Téléchargement', 'player.saving': 'Enregistrement', 'player.readyTitle': 'Téléchargement prêt', 'player.readyBody': "La vidéo est enregistrée dans l'espace privé de Drovixa.",
    'search.placeholder': 'Séries, films, acteurs, genres…', 'search.trending': 'Recherches populaires', 'search.searching': 'Recherche…', 'search.emptyTitle': 'Aucun résultat', 'search.emptyBody': 'Essayez un autre titre, acteur, genre ou mot-clé.',
    'content.play': 'Lire', 'content.saved': 'Enregistré', 'content.myList': 'Ma liste', 'content.genres': 'Genres', 'content.cast': 'Distribution', 'content.episodes': 'Épisodes', 'content.noEpisodes': 'Aucun épisode', 'content.noEpisodesBody': 'Les épisodes publiés apparaîtront ici.', 'content.movie': 'Film', 'content.episodeCount': '{count} épisodes',
    'devices.title': 'Vos appareils', 'devices.subtitle': 'Vérifiez les appareils connectés et retirez ceux que vous ne reconnaissez pas.', 'devices.current': 'APPAREIL ACTUEL', 'devices.remove': 'Retirer', 'devices.confirm': "Déconnecter l'appareil ?",
  },
  'pt-BR': {
    'nav.home': 'Início', 'nav.discover': 'Descobrir', 'nav.shorts': 'Curtos', 'nav.library': 'Minha lista', 'nav.profile': 'Perfil',
    'common.loading': 'Carregando…', 'common.retry': 'Tentar novamente', 'common.errorTitle': 'Algo deu errado', 'common.errorBody': 'Verifique sua conexão e tente novamente.', 'common.signIn': 'Entrar', 'common.cancel': 'Cancelar', 'common.delete': 'Excluir',
    'home.featured': 'DESTAQUE', 'home.original': 'ORIGINAL DROVIXA', 'home.watch': 'Assistir agora', 'home.more': 'Mais informações', 'home.emptyTitle': 'Catálogo conectado', 'home.emptyBody': 'O conteúdo publicado aparecerá aqui automaticamente.',
    'discover.eyebrow': 'ENCONTRE SUA PRÓXIMA PAIXÃO', 'discover.search': 'Séries, filmes, atores…', 'discover.all': 'Todos os estilos', 'discover.popular': 'Popular', 'discover.new': 'Novos', 'discover.rating': 'Avaliação', 'discover.emptyTitle': 'Nada encontrado', 'discover.emptyBody': 'Tente outro gênero.',
    'library.eyebrow': 'SEU ESPAÇO', 'library.title': 'Minha lista', 'library.guestTitle': 'Mantenha todas as histórias por perto', 'library.guestBody': 'Entre para sincronizar séries e filmes salvos em seus dispositivos.', 'library.emptyTitle': 'Sua lista está vazia', 'library.emptyBody': 'Salve uma série ou filme para vê-lo aqui.',
    'profile.eyebrow': 'CONTA', 'profile.title': 'Perfil', 'profile.guest': 'Modo visitante', 'profile.guestBody': 'Entre para desbloquear sua experiência Drovixa personalizada.', 'profile.createAccount': 'Criar conta', 'profile.signOut': 'Sair', 'profile.signingOut': 'Saindo…',
    'profile.profiles': 'Perfis', 'profile.premium': 'Premium', 'profile.coins': 'Moedas', 'profile.rewards': 'Recompensas e indicações', 'profile.myList': 'Minha lista', 'profile.downloads': 'Downloads', 'profile.notifications': 'Notificações', 'profile.language': 'Idioma', 'profile.subtitles': 'Configurações de legendas', 'profile.playback': 'Reprodução', 'profile.devices': 'Dispositivos', 'profile.security': 'Segurança', 'profile.help': 'Central de ajuda',
    'language.title': 'Idioma', 'language.subtitle': 'Escolha o idioma usado em todo o Drovixa.', 'language.device': 'O Drovixa segue o idioma do celular até você escolher um.',
    'playback.title': 'Reprodução', 'playback.subtitle': 'Controle como os vídeos iniciam neste dispositivo.', 'playback.autoplay': 'Reprodução automática', 'playback.autoplayBody': 'Iniciar o vídeo após a autorização segura.',
    'help.title': 'Central de ajuda', 'help.subtitle': 'Respostas rápidas e suporte direto quando você precisar.', 'help.search': 'Pesquisar ajuda', 'help.contact': 'Falar com o suporte', 'help.email': 'Enviar e-mail ao suporte Drovixa', 'help.faq1q': 'Por que um vídeo não reproduz?', 'help.faq1a': 'Verifique sua conexão e toque em Tentar novamente. Se continuar, envie ao suporte o erro exibido.', 'help.faq2q': 'Como funcionam os downloads?', 'help.faq2a': 'Assinantes Premium podem salvar vídeos elegíveis. O Drovixa prepara a cópia offline, baixa para o armazenamento privado e verifica a licença.', 'help.faq3q': 'Como altero o idioma?', 'help.faq3a': 'Abra Perfil, escolha Idioma e selecione um dos cinco idiomas.',
    'security.title': 'Segurança', 'security.subtitle': 'Proteja sua conta e veja onde ela está conectada.', 'security.devices': 'Ver dispositivos conectados', 'security.logoutAll': 'Sair de todos os dispositivos', 'security.logoutConfirm': 'Sair de todos os lugares?', 'security.logoutBody': 'Todas as sessões Drovixa, incluindo este celular, serão encerradas.', 'security.done': 'Todas as sessões foram encerradas.', 'security.password': 'Alterar senha', 'security.current': 'Senha atual', 'security.new': 'Nova senha', 'security.confirm': 'Confirmar nova senha', 'security.update': 'Atualizar senha', 'security.updated': 'Senha atualizada com sucesso.',
    'notifications.guestTitle': 'Continue na história', 'notifications.guestBody': 'Entre para receber novos episódios e alertas de conta e segurança.', 'notifications.emptyTitle': 'Nenhuma notificação', 'notifications.emptyBody': 'As novidades do Drovixa aparecerão aqui.',
    'downloads.eyebrow': 'OFFLINE E PRIVADO', 'downloads.title': 'Downloads', 'downloads.subtitle': 'Os vídeos ficam no armazenamento privado do Drovixa e param quando a licença expira.', 'downloads.emptyTitle': 'Nenhum download', 'downloads.emptyBody': 'Use Baixar no player de um filme ou episódio.', 'downloads.expired': 'LICENÇA EXPIRADA', 'downloads.validUntil': 'VÁLIDO ATÉ {date}', 'downloads.deleteTitle': 'Excluir download?',
    'player.authorizing': 'Autorizando reprodução segura…', 'player.unavailable': 'Reprodução indisponível', 'player.tryLater': 'Tente novamente mais tarde.', 'player.failed': 'Falha ao reproduzir o vídeo.', 'player.refresh': 'Atualize o link seguro e tente novamente.', 'player.retry': 'Tentar reproduzir novamente', 'player.pause': 'Pausar', 'player.play': 'Reproduzir', 'player.download': 'Baixar', 'player.preparing': 'Preparando', 'player.downloading': 'Baixando', 'player.saving': 'Salvando', 'player.readyTitle': 'Download pronto', 'player.readyBody': 'O vídeo foi salvo no armazenamento privado do Drovixa.',
    'search.placeholder': 'Séries, filmes, atores, gêneros…', 'search.trending': 'Pesquisas em alta', 'search.searching': 'Pesquisando…', 'search.emptyTitle': 'Nenhum resultado', 'search.emptyBody': 'Tente outro título, ator, gênero ou palavra-chave.',
    'content.play': 'Reproduzir', 'content.saved': 'Salvo', 'content.myList': 'Minha lista', 'content.genres': 'Gêneros', 'content.cast': 'Elenco', 'content.episodes': 'Episódios', 'content.noEpisodes': 'Nenhum episódio', 'content.noEpisodesBody': 'Os episódios publicados aparecerão aqui.', 'content.movie': 'Filme', 'content.episodeCount': '{count} episódios',
    'devices.title': 'Seus dispositivos', 'devices.subtitle': 'Revise os dispositivos conectados e remova os que não reconhece.', 'devices.current': 'DISPOSITIVO ATUAL', 'devices.remove': 'Remover', 'devices.confirm': 'Sair do dispositivo?',
  },
  es: {
    'nav.home': 'Inicio', 'nav.discover': 'Descubrir', 'nav.shorts': 'Cortos', 'nav.library': 'Mi lista', 'nav.profile': 'Perfil',
    'common.loading': 'Cargando…', 'common.retry': 'Reintentar', 'common.errorTitle': 'Algo salió mal', 'common.errorBody': 'Comprueba tu conexión e inténtalo de nuevo.', 'common.signIn': 'Iniciar sesión', 'common.cancel': 'Cancelar', 'common.delete': 'Eliminar',
    'home.featured': 'DESTACADO', 'home.original': 'ORIGINAL DE DROVIXA', 'home.watch': 'Ver ahora', 'home.more': 'Más información', 'home.emptyTitle': 'Catálogo conectado', 'home.emptyBody': 'El contenido publicado aparecerá aquí automáticamente.',
    'discover.eyebrow': 'ENCUENTRA TU PRÓXIMA OBSESIÓN', 'discover.search': 'Series, películas, actores…', 'discover.all': 'Todos los estilos', 'discover.popular': 'Popular', 'discover.new': 'Nuevos', 'discover.rating': 'Valoración', 'discover.emptyTitle': 'No se encontró nada', 'discover.emptyBody': 'Prueba otro género.',
    'library.eyebrow': 'TU ESPACIO', 'library.title': 'Mi lista', 'library.guestTitle': 'Mantén todas tus historias cerca', 'library.guestBody': 'Inicia sesión para sincronizar series y películas guardadas entre dispositivos.', 'library.emptyTitle': 'Tu lista está vacía', 'library.emptyBody': 'Guarda una serie o película y aparecerá aquí.',
    'profile.eyebrow': 'CUENTA', 'profile.title': 'Perfil', 'profile.guest': 'Modo invitado', 'profile.guestBody': 'Inicia sesión para desbloquear tu experiencia Drovixa personalizada.', 'profile.createAccount': 'Crear cuenta', 'profile.signOut': 'Cerrar sesión', 'profile.signingOut': 'Cerrando sesión…',
    'profile.profiles': 'Perfiles', 'profile.premium': 'Premium', 'profile.coins': 'Monedas', 'profile.rewards': 'Recompensas y referidos', 'profile.myList': 'Mi lista', 'profile.downloads': 'Descargas', 'profile.notifications': 'Notificaciones', 'profile.language': 'Idioma', 'profile.subtitles': 'Ajustes de subtítulos', 'profile.playback': 'Reproducción', 'profile.devices': 'Dispositivos', 'profile.security': 'Seguridad', 'profile.help': 'Centro de ayuda',
    'language.title': 'Idioma', 'language.subtitle': 'Elige el idioma que usará Drovixa.', 'language.device': 'Drovixa sigue el idioma del teléfono hasta que elijas uno.',
    'playback.title': 'Reproducción', 'playback.subtitle': 'Controla cómo comienzan los videos en este dispositivo.', 'playback.autoplay': 'Reproducción automática', 'playback.autoplayBody': 'Iniciar el video después de la autorización segura.',
    'help.title': 'Centro de ayuda', 'help.subtitle': 'Respuestas rápidas y soporte directo cuando lo necesites.', 'help.search': 'Buscar ayuda', 'help.contact': 'Contactar con soporte', 'help.email': 'Enviar correo a soporte de Drovixa', 'help.faq1q': '¿Por qué no se reproduce un video?', 'help.faq1a': 'Comprueba tu conexión y pulsa Reintentar. Si continúa, envía a soporte el error que aparece.', 'help.faq2q': '¿Cómo funcionan las descargas?', 'help.faq2a': 'Los miembros Premium pueden guardar videos elegibles. Drovixa prepara la copia sin conexión, la descarga en el espacio privado y comprueba su licencia.', 'help.faq3q': '¿Cómo cambio el idioma?', 'help.faq3a': 'Abre Perfil, elige Idioma y selecciona uno de los cinco idiomas.',
    'security.title': 'Seguridad', 'security.subtitle': 'Protege tu cuenta y revisa dónde está conectada.', 'security.devices': 'Revisar dispositivos conectados', 'security.logoutAll': 'Cerrar sesión en todos los dispositivos', 'security.logoutConfirm': '¿Cerrar sesión en todas partes?', 'security.logoutBody': 'Se cerrarán todas las sesiones Drovixa, incluido este teléfono.', 'security.done': 'Se cerraron todas las sesiones.', 'security.password': 'Cambiar contraseña', 'security.current': 'Contraseña actual', 'security.new': 'Nueva contraseña', 'security.confirm': 'Confirmar nueva contraseña', 'security.update': 'Actualizar contraseña', 'security.updated': 'Contraseña actualizada correctamente.',
    'notifications.guestTitle': 'Sigue dentro de la historia', 'notifications.guestBody': 'Inicia sesión para recibir nuevos episodios y alertas de cuenta y seguridad.', 'notifications.emptyTitle': 'No hay notificaciones', 'notifications.emptyBody': 'Las novedades de Drovixa aparecerán aquí.',
    'downloads.eyebrow': 'SIN CONEXIÓN Y PRIVADO', 'downloads.title': 'Descargas', 'downloads.subtitle': 'Los videos permanecen en el espacio privado de Drovixa y dejan de funcionar al vencer la licencia.', 'downloads.emptyTitle': 'Aún no hay descargas', 'downloads.emptyBody': 'Usa Descargar desde el reproductor de una película o episodio.', 'downloads.expired': 'LICENCIA VENCIDA', 'downloads.validUntil': 'VÁLIDO HASTA {date}', 'downloads.deleteTitle': '¿Eliminar descarga?',
    'player.authorizing': 'Autorizando reproducción segura…', 'player.unavailable': 'Reproducción no disponible', 'player.tryLater': 'Inténtalo de nuevo más tarde.', 'player.failed': 'No se pudo reproducir el video.', 'player.refresh': 'Actualiza el enlace seguro e inténtalo de nuevo.', 'player.retry': 'Reintentar reproducción', 'player.pause': 'Pausar', 'player.play': 'Reproducir', 'player.download': 'Descargar', 'player.preparing': 'Preparando', 'player.downloading': 'Descargando', 'player.saving': 'Guardando', 'player.readyTitle': 'Descarga lista', 'player.readyBody': 'El video se guardó en el espacio privado de Drovixa.',
    'search.placeholder': 'Series, películas, actores, géneros…', 'search.trending': 'Búsquedas populares', 'search.searching': 'Buscando…', 'search.emptyTitle': 'Sin resultados', 'search.emptyBody': 'Prueba con otro título, actor, género o palabra clave.',
    'content.play': 'Reproducir', 'content.saved': 'Guardado', 'content.myList': 'Mi lista', 'content.genres': 'Géneros', 'content.cast': 'Reparto', 'content.episodes': 'Episodios', 'content.noEpisodes': 'Aún no hay episodios', 'content.noEpisodesBody': 'Los episodios publicados aparecerán aquí.', 'content.movie': 'Película', 'content.episodeCount': '{count} episodios',
    'devices.title': 'Tus dispositivos', 'devices.subtitle': 'Revisa los dispositivos conectados y elimina los que no reconozcas.', 'devices.current': 'DISPOSITIVO ACTUAL', 'devices.remove': 'Eliminar', 'devices.confirm': '¿Cerrar sesión en el dispositivo?',
  },
} as const;

type TranslationKey = keyof typeof translations.en;
type Variables = Record<string, string | number>;

const KEY = 'drovixa.language.v1';

function detectedLanguage(): LanguageCode {
  const tag = getLocales()[0]?.languageTag?.toLowerCase() ?? 'en';
  if (tag.startsWith('ht')) return 'ht';
  if (tag.startsWith('fr')) return 'fr';
  if (tag.startsWith('pt')) return 'pt-BR';
  if (tag.startsWith('es')) return 'es';
  return 'en';
}

function translate(language: LanguageCode, key: TranslationKey, variables?: Variables): string {
  const catalog = translations[language] as Partial<Record<TranslationKey, string>>;
  let value: string = catalog[key] ?? translations.en[key];
  if (variables) {
    Object.entries(variables).forEach(([name, replacement]) => {
      value = value.replaceAll(`{${name}}`, String(replacement));
    });
  }
  return value;
}

type LanguageState = {
  language: LanguageCode;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  setLanguage: (language: LanguageCode) => Promise<void>;
};

export const useLanguageStore = create<LanguageState>((set) => ({
  language: 'en',
  hydrated: false,
  hydrate: async () => {
    const saved = await SecureStore.getItemAsync(KEY);
    const supported = languages.some((item) => item.code === saved);
    set({ language: supported ? saved as LanguageCode : detectedLanguage(), hydrated: true });
  },
  setLanguage: async (language) => {
    await SecureStore.setItemAsync(KEY, language);
    set({ language });
  },
}));

export function useI18n() {
  const language = useLanguageStore((state) => state.language);
  const setLanguage = useLanguageStore((state) => state.setLanguage);
  return {
    language,
    locale: language === 'pt-BR' ? 'pt-BR' : language,
    setLanguage,
    t: (key: TranslationKey, variables?: Variables) => translate(language, key, variables),
  };
}
