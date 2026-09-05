# ruff: noqa: E501
from __future__ import annotations

import argparse
import asyncio
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid5

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionFactory, dispose_database
from app.models.base import utcnow
from app.models.catalog import Country, Genre, Language
from app.models.content import Content, Episode, Season, Series, VideoAsset
from app.models.enums import (
    AgeRating,
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    SeriesStatus,
    VideoStatus,
)

DEMO_BATCH = "showcase-v1"
DEMO_PROVIDER = "drovixa_demo"
NAMESPACE = UUID("37cb529f-2a86-4f50-900f-524838714b91")
LANGUAGES = ("en", "fr", "pt-BR", "es", "ht")

DESCRIPTION_SUFFIX = {
    "en": "This original Drovixa showcase story is presented with two short demo episodes.",
    "fr": "Cette histoire originale de démonstration Drovixa propose deux courts épisodes.",
    "pt-BR": "Esta história original de demonstração do Drovixa tem dois episódios curtos.",
    "es": "Esta historia original de demostración de Drovixa incluye dos episodios cortos.",
    "ht": "Istwa orijinal demonstrasyon Drovixa sa a gen de ti epizòd kout.",
}

EPISODE_COPY = {
    "en": (
        ("The Arrival", "A first encounter changes the direction of the story."),
        ("The Choice", "A difficult choice opens the door to what comes next."),
    ),
    "fr": (
        ("L'arrivée", "Une première rencontre change le cours de l'histoire."),
        ("Le choix", "Un choix difficile ouvre la porte à la suite."),
    ),
    "pt-BR": (
        ("A chegada", "Um primeiro encontro muda o rumo da história."),
        ("A escolha", "Uma escolha difícil abre a porta para o que vem depois."),
    ),
    "es": (
        ("La llegada", "Un primer encuentro cambia el rumbo de la historia."),
        ("La decisión", "Una decisión difícil abre la puerta a lo que sigue."),
    ),
    "ht": (
        ("Rive a", "Yon premye rankont chanje direksyon istwa a."),
        ("Chwa a", "Yon chwa difisil louvri pòt pou sa k ap vini an."),
    ),
}

SERIES = (
    {
        "slug": "midnight-in-jacmel",
        "country": "HT",
        "language": "ht",
        "genres": ("romance", "mystery"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "Midnight in Jacmel",
                "A muralist and a radio host follow a midnight signal through Jacmel's painted streets.",
            ),
            "fr": (
                "Minuit à Jacmel",
                "Une muraliste et un animateur radio suivent un signal de minuit dans les rues peintes de Jacmel.",
            ),
            "pt-BR": (
                "Meia-noite em Jacmel",
                "Uma muralista e um radialista seguem um sinal da meia-noite pelas ruas coloridas de Jacmel.",
            ),
            "es": (
                "Medianoche en Jacmel",
                "Una muralista y un locutor siguen una señal de medianoche por las calles pintadas de Jacmel.",
            ),
            "ht": (
                "Minwi nan Jakmèl",
                "Yon atis miray ak yon animatè radyo suiv yon siyal minwi nan lari pentire Jakmèl yo.",
            ),
        },
    },
    {
        "slug": "the-last-mango-tree",
        "country": "HT",
        "language": "ht",
        "genres": ("family", "drama"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "The Last Mango Tree",
                "Three siblings reunite to save the family garden and uncover a letter hidden for twenty years.",
            ),
            "fr": (
                "Le dernier manguier",
                "Trois frères et sœurs se retrouvent pour sauver le jardin familial et découvrent une lettre cachée depuis vingt ans.",
            ),
            "pt-BR": (
                "A última mangueira",
                "Três irmãos se reencontram para salvar o jardim da família e descobrem uma carta escondida há vinte anos.",
            ),
            "es": (
                "El último árbol de mango",
                "Tres hermanos se reúnen para salvar el jardín familiar y descubren una carta oculta durante veinte años.",
            ),
            "ht": (
                "Dènye pye mango a",
                "Twa frè ak sè reyini pou sove jaden fanmi an epi yo dekouvri yon lèt ki te kache pandan ven ane.",
            ),
        },
    },
    {
        "slug": "ceo-by-sunrise",
        "country": "US",
        "language": "en",
        "genres": ("billionaire", "comedy", "romance"),
        "orientation": "vertical",
        "copy": {
            "en": (
                "CEO by Sunrise",
                "An overnight intern is mistaken for the new CEO and has until sunrise to fix the company's biggest crisis.",
            ),
            "fr": (
                "PDG au lever du soleil",
                "Une stagiaire de nuit est prise pour la nouvelle PDG et doit résoudre la plus grande crise de l'entreprise avant l'aube.",
            ),
            "pt-BR": (
                "CEO ao amanhecer",
                "Uma estagiária noturna é confundida com a nova CEO e tem até o amanhecer para resolver a maior crise da empresa.",
            ),
            "es": (
                "CEO al amanecer",
                "Una becaria nocturna es confundida con la nueva CEO y tiene hasta el amanecer para resolver la mayor crisis de la empresa.",
            ),
            "ht": (
                "PDG anvan solèy leve",
                "Yo pran yon estajyè lannuit pou nouvo PDG a, epi li gen jis solèy leve pou rezoud pi gwo kriz konpayi an.",
            ),
        },
    },
    {
        "slug": "port-au-prince-2099",
        "country": "HT",
        "language": "ht",
        "genres": ("action", "fantasy"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "Port-au-Prince 2099",
                "A young engineer awakens an ancient map that can power the city—or erase it.",
            ),
            "fr": (
                "Port-au-Prince 2099",
                "Une jeune ingénieure réveille une carte ancienne capable d'alimenter la ville ou de l'effacer.",
            ),
            "pt-BR": (
                "Porto Príncipe 2099",
                "Uma jovem engenheira desperta um mapa antigo capaz de energizar a cidade ou apagá-la.",
            ),
            "es": (
                "Puerto Príncipe 2099",
                "Una joven ingeniera despierta un mapa antiguo capaz de dar energía a la ciudad o borrarla.",
            ),
            "ht": (
                "Pòtoprens 2099",
                "Yon jèn enjenyè reveye yon kat ansyen ki ka bay vil la enèji oswa efase l nèt.",
            ),
        },
    },
    {
        "slug": "the-sapphire-crown",
        "country": "GB",
        "language": "en",
        "genres": ("historical", "romance"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "The Sapphire Crown",
                "A palace archivist finds proof that the kingdom's missing heir may still be alive.",
            ),
            "fr": (
                "La couronne de saphir",
                "Une archiviste du palais découvre la preuve que l'héritier disparu du royaume serait encore en vie.",
            ),
            "pt-BR": (
                "A coroa de safira",
                "Uma arquivista do palácio encontra provas de que o herdeiro desaparecido do reino ainda pode estar vivo.",
            ),
            "es": (
                "La corona de zafiro",
                "Una archivera del palacio encuentra pruebas de que el heredero perdido del reino podría seguir vivo.",
            ),
            "ht": (
                "Kouwòn safi a",
                "Yon achivis palè jwenn prèv eritye wayòm nan ki te disparèt la ka toujou vivan.",
            ),
        },
    },
    {
        "slug": "secrets-of-sao-paulo",
        "country": "BR",
        "language": "pt-BR",
        "genres": ("crime", "thriller"),
        "orientation": "vertical",
        "copy": {
            "en": (
                "Secrets of São Paulo",
                "A bike courier receives the wrong package and becomes the only witness to a citywide conspiracy.",
            ),
            "fr": (
                "Les secrets de São Paulo",
                "Une coursière à vélo reçoit le mauvais colis et devient l'unique témoin d'un complot à l'échelle de la ville.",
            ),
            "pt-BR": (
                "Segredos de São Paulo",
                "Uma entregadora de bicicleta recebe o pacote errado e vira a única testemunha de uma conspiração pela cidade.",
            ),
            "es": (
                "Secretos de São Paulo",
                "Una repartidora en bicicleta recibe el paquete equivocado y se convierte en la única testigo de una conspiración urbana.",
            ),
            "ht": (
                "Sekrè São Paulo",
                "Yon livrezè bisiklèt resevwa move pake a epi li vin sèl temwen yon konplo ki gaye nan tout vil la.",
            ),
        },
    },
    {
        "slug": "paris-after-rain",
        "country": "FR",
        "language": "fr",
        "genres": ("romance", "drama"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "Paris After Rain",
                "Two former friends share one umbrella and a secret that neither has forgotten.",
            ),
            "fr": (
                "Paris après la pluie",
                "Deux anciens amis partagent un parapluie et un secret qu'aucun des deux n'a oublié.",
            ),
            "pt-BR": (
                "Paris depois da chuva",
                "Dois antigos amigos dividem um guarda-chuva e um segredo que nenhum deles esqueceu.",
            ),
            "es": (
                "París después de la lluvia",
                "Dos antiguos amigos comparten un paraguas y un secreto que ninguno ha olvidado.",
            ),
            "ht": (
                "Pari apre lapli",
                "De ansyen zanmi pataje yon parapli ak yon sekrè okenn nan yo pa janm bliye.",
            ),
        },
    },
    {
        "slug": "havana-frequency",
        "country": "MX",
        "language": "es",
        "genres": ("mystery", "crime"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "Havana Frequency",
                "A sound engineer hears tomorrow's crimes hidden inside an abandoned radio frequency.",
            ),
            "fr": (
                "Fréquence La Havane",
                "Un ingénieur du son entend les crimes de demain cachés dans une fréquence radio abandonnée.",
            ),
            "pt-BR": (
                "Frequência Havana",
                "Um engenheiro de som ouve os crimes de amanhã escondidos em uma frequência de rádio abandonada.",
            ),
            "es": (
                "Frecuencia Habana",
                "Un ingeniero de sonido escucha los crímenes de mañana ocultos en una frecuencia de radio abandonada.",
            ),
            "ht": (
                "Frekans La Avàn",
                "Yon enjenyè son tande krim demen yo kache andedan yon frekans radyo abandone.",
            ),
        },
    },
    {
        "slug": "lagos-moon",
        "country": "GB",
        "language": "en",
        "genres": ("fantasy", "romance"),
        "orientation": "vertical",
        "copy": {
            "en": (
                "Lagos Moon",
                "Each full moon, a chef remembers one day from a life she never lived.",
            ),
            "fr": (
                "La lune de Lagos",
                "À chaque pleine lune, une cheffe se souvient d'un jour d'une vie qu'elle n'a jamais vécue.",
            ),
            "pt-BR": (
                "Lua de Lagos",
                "A cada lua cheia, uma chef se lembra de um dia de uma vida que nunca viveu.",
            ),
            "es": (
                "Luna de Lagos",
                "Con cada luna llena, una chef recuerda un día de una vida que nunca vivió.",
            ),
            "ht": (
                "Lalin Lagos",
                "Chak fwa lalin nan plen, yon chèf kizin sonje yon jou nan yon lavi li pa t janm viv.",
            ),
        },
    },
    {
        "slug": "the-lisbon-heist",
        "country": "ES",
        "language": "pt-BR",
        "genres": ("crime", "action"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "The Lisbon Heist",
                "Four strangers plan a theft where the real target is not money, but a forgotten name.",
            ),
            "fr": (
                "Le braquage de Lisbonne",
                "Quatre inconnus préparent un vol dont la vraie cible n'est pas l'argent, mais un nom oublié.",
            ),
            "pt-BR": (
                "O assalto de Lisboa",
                "Quatro desconhecidos planejam um roubo cujo verdadeiro alvo não é dinheiro, mas um nome esquecido.",
            ),
            "es": (
                "El golpe de Lisboa",
                "Cuatro desconocidos planean un robo cuyo verdadero objetivo no es dinero, sino un nombre olvidado.",
            ),
            "ht": (
                "Gwo vòl Lisbon nan",
                "Kat etranje prepare yon vòl kote vrè sib la se pa lajan, men yon non tout moun bliye.",
            ),
        },
    },
    {
        "slug": "campus-27",
        "country": "CA",
        "language": "fr",
        "genres": ("mystery", "drama"),
        "orientation": "vertical",
        "copy": {
            "en": (
                "Campus 27",
                "Five students discover that the closed floor of their residence is broadcasting their private conversations.",
            ),
            "fr": (
                "Campus 27",
                "Cinq étudiants découvrent que l'étage condamné de leur résidence diffuse leurs conversations privées.",
            ),
            "pt-BR": (
                "Campus 27",
                "Cinco estudantes descobrem que o andar interditado da residência transmite suas conversas privadas.",
            ),
            "es": (
                "Campus 27",
                "Cinco estudiantes descubren que la planta cerrada de su residencia transmite sus conversaciones privadas.",
            ),
            "ht": (
                "Kanpis 27",
                "Senk etidyan dekouvri etaj rezidans yo te fèmen an ap difize konvèsasyon prive yo.",
            ),
        },
    },
    {
        "slug": "the-borrowed-bride",
        "country": "US",
        "language": "en",
        "genres": ("comedy", "romance"),
        "orientation": "vertical",
        "copy": {
            "en": (
                "The Borrowed Bride",
                "A wedding planner poses as a runaway bride and accidentally falls for the groom's suspicious sister.",
            ),
            "fr": (
                "La mariée empruntée",
                "Une organisatrice de mariage se fait passer pour une mariée en fuite et tombe sous le charme de la sœur méfiante du marié.",
            ),
            "pt-BR": (
                "A noiva emprestada",
                "Uma cerimonialista se passa por uma noiva fugitiva e se apaixona pela desconfiada irmã do noivo.",
            ),
            "es": (
                "La novia prestada",
                "Una organizadora de bodas se hace pasar por una novia fugitiva y se enamora de la desconfiada hermana del novio.",
            ),
            "ht": (
                "Lamarye prete a",
                "Yon òganizatris maryaj pran pòz yon lamarye ki sove epi li tonbe damou pou sè mesye a ki pa fè l konfyans.",
            ),
        },
    },
    {
        "slug": "bloodline-of-the-bayou",
        "country": "US",
        "language": "en",
        "genres": ("fantasy", "mystery"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "Bloodline of the Bayou",
                "A medical student returns home and learns why her family never goes outside after moonrise.",
            ),
            "fr": (
                "Le sang du bayou",
                "Une étudiante en médecine rentre chez elle et découvre pourquoi sa famille ne sort jamais après le lever de la lune.",
            ),
            "pt-BR": (
                "Sangue do pântano",
                "Uma estudante de medicina volta para casa e descobre por que sua família nunca sai depois que a lua nasce.",
            ),
            "es": (
                "Sangre del pantano",
                "Una estudiante de medicina vuelve a casa y descubre por qué su familia nunca sale después de que aparece la luna.",
            ),
            "ht": (
                "San marekaj la",
                "Yon etidyan medsin retounen lakay li epi li aprann poukisa fanmi li pa janm soti apre lalin leve.",
            ),
        },
    },
    {
        "slug": "the-silent-witness",
        "country": "CA",
        "language": "fr",
        "genres": ("revenge", "thriller"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "The Silent Witness",
                "A court illustrator recognizes the accused as the person who destroyed her family.",
            ),
            "fr": (
                "Le témoin silencieux",
                "Une dessinatrice judiciaire reconnaît dans l'accusé la personne qui a détruit sa famille.",
            ),
            "pt-BR": (
                "A testemunha silenciosa",
                "Uma ilustradora de tribunal reconhece no acusado a pessoa que destruiu sua família.",
            ),
            "es": (
                "La testigo silenciosa",
                "Una ilustradora judicial reconoce en el acusado a la persona que destruyó a su familia.",
            ),
            "ht": (
                "Temwen ki pa pale a",
                "Yon desenatris tribinal rekonèt akize a kòm moun ki te detwi fanmi li.",
            ),
        },
    },
    {
        "slug": "three-families",
        "country": "US",
        "language": "es",
        "genres": ("family", "drama"),
        "orientation": "horizontal",
        "copy": {
            "en": (
                "Three Families",
                "A neighborhood blackout brings three households together around one table and one impossible truth.",
            ),
            "fr": (
                "Trois familles",
                "Une panne de quartier réunit trois foyers autour d'une même table et d'une vérité impossible.",
            ),
            "pt-BR": (
                "Três famílias",
                "Um apagão no bairro reúne três famílias à mesma mesa diante de uma verdade impossível.",
            ),
            "es": (
                "Tres familias",
                "Un apagón en el barrio reúne a tres hogares alrededor de una mesa y una verdad imposible.",
            ),
            "ht": (
                "Twa fanmi",
                "Yon blakawout nan katye a mete twa fanmi bò menm tab la devan yon verite ki sanble enposib.",
            ),
        },
    },
)


def stable_id(*parts: object) -> UUID:
    return uuid5(NAMESPACE, ":".join(str(part) for part in parts))


def translations(copy: dict[str, tuple[str, str]]) -> dict[str, dict[str, str]]:
    return {
        language: {
            "title": title,
            "short_description": summary,
            "description": f"{summary} {DESCRIPTION_SUFFIX[language]}",
            "seo_title": f"{title} | Drovixa",
            "seo_description": summary,
        }
        for language, (title, summary) in copy.items()
    }


def episode_translations(number: int) -> dict[str, dict[str, str]]:
    return {
        language: {
            "title": f"{('Episode' if language == 'en' else 'Épisode' if language == 'fr' else 'Episódio' if language == 'pt-BR' else 'Episodio' if language == 'es' else 'Epizòd')} {number} · {EPISODE_COPY[language][number - 1][0]}",
            "description": EPISODE_COPY[language][number - 1][1],
        }
        for language in LANGUAGES
    }


async def remove_demo_catalog(db: AsyncSession) -> int:
    content_ids = list(await db.scalars(select(Content.id).where(Content.demo_batch == DEMO_BATCH)))
    if not content_ids:
        return 0
    asset_ids = list(
        await db.scalars(
            select(Episode.video_asset_id).where(
                Episode.series_id.in_(content_ids), Episode.video_asset_id.is_not(None)
            )
        )
    )
    await db.execute(delete(Content).where(Content.id.in_(content_ids)))
    await db.flush()
    if asset_ids:
        await db.execute(delete(VideoAsset).where(VideoAsset.id.in_(asset_ids)))
    return len(content_ids)


async def sync_demo_catalog(db: AsyncSession) -> int:
    settings = get_settings()
    base_url = settings.DEMO_MEDIA_BASE_URL.rstrip("/")
    languages = {row.code: row for row in await db.scalars(select(Language))}
    countries = {row.code: row for row in await db.scalars(select(Country))}
    genres = {row.slug: row for row in await db.scalars(select(Genre))}
    now = utcnow()

    for index, item in enumerate(SERIES, start=1):
        slug = str(item["slug"])
        content_id = stable_id(DEMO_BATCH, "content", slug)
        content = await db.get(Content, content_id)
        if content is None:
            content = Content(id=content_id, type=ContentType.SERIES, title="", slug=slug)
            db.add(content)
        localized = translations(cast(dict[str, tuple[str, str]], item["copy"]))
        english = localized["en"]
        original_language = str(item["language"])
        content.type = ContentType.SERIES
        content.title = str(english["title"])
        content.original_title = localized[original_language]["title"]
        content.slug = slug
        content.short_description = english["short_description"]
        content.description = english["description"]
        content.translations = localized
        content.demo_batch = DEMO_BATCH
        content.poster_url = f"{base_url}/posters/{slug}.jpg"
        content.backdrop_url = f"{base_url}/backdrops/{slug}.jpg"
        content.release_date = date(2026, ((index - 1) % 9) + 1, min(index + 2, 28))
        content.country = countries.get(str(item["country"]))
        content.original_language = languages.get(original_language)
        content.age_rating = AgeRating.THIRTEEN_PLUS
        content.status = ContentStatus.PUBLISHED
        content.visibility = ContentVisibility.PUBLIC
        content.featured = index <= 5
        content.premium = False
        content.rating = Decimal(str(round(9.2 - index * 0.08, 2)))
        content.rating_count = 410 - index * 13
        content.view_count = 5200 - index * 173
        content.like_count = 980 - index * 29
        content.allowed_countries = []
        content.blocked_countries = []
        content.seo_title = english["seo_title"]
        content.seo_description = english["seo_description"]
        content.published_at = now
        content.deleted_at = None
        content.genres = [genres[slug] for slug in item["genres"] if slug in genres]

        series = await db.get(Series, content_id)
        orientation = Orientation(str(item["orientation"]))
        if series is None:
            series = Series(id=content_id, content=content)
            db.add(series)
        series.total_seasons = 1
        series.total_episodes = 2
        series.series_status = SeriesStatus.ONGOING
        series.orientation = orientation

        season_id = stable_id(DEMO_BATCH, "season", slug, 1)
        season = await db.get(Season, season_id)
        if season is None:
            season = Season(id=season_id, series=series, season_number=1)
            db.add(season)
        season.title = "Season 1"
        season.description = "Drovixa showcase demo season."
        season.poster_url = content.poster_url
        season.release_date = content.release_date
        season.status = ContentStatus.PUBLISHED
        season.sort_order = 1
        season.deleted_at = None

        for episode_number in (1, 2):
            clip = f"{orientation.value}-{episode_number:02d}"
            asset_id = stable_id(DEMO_BATCH, "asset", slug, episode_number)
            asset = await db.get(VideoAsset, asset_id)
            if asset is None:
                asset = VideoAsset(
                    id=asset_id,
                    provider=DEMO_PROVIDER,
                    provider_asset_id=f"{DEMO_BATCH}:{slug}:{episode_number}",
                )
                db.add(asset)
            asset.status = VideoStatus.READY
            asset.duration_seconds = 12
            asset.width = 720
            asset.height = 405 if orientation == Orientation.HORIZONTAL else 1280
            asset.aspect_ratio = "16:9" if orientation == Orientation.HORIZONTAL else "9:16"
            asset.thumbnail_url = f"{base_url}/backdrops/{slug}.jpg"
            asset.playback_id = clip
            asset.ready_at = now
            asset.asset_metadata = {"demo_batch": DEMO_BATCH, "bundled": True}
            asset.deleted_at = None

            episode_id = stable_id(DEMO_BATCH, "episode", slug, episode_number)
            episode = await db.get(Episode, episode_id)
            localized_episode = episode_translations(episode_number)
            if episode is None:
                episode = Episode(
                    id=episode_id,
                    series=series,
                    season=season,
                    episode_number=episode_number,
                    title=localized_episode["en"]["title"],
                )
                db.add(episode)
            episode.series = series
            episode.season = season
            episode.episode_number = episode_number
            episode.title = localized_episode["en"]["title"]
            episode.description = localized_episode["en"]["description"]
            episode.translations = localized_episode
            episode.thumbnail_url = content.backdrop_url
            episode.duration_seconds = 12
            episode.video_asset = asset
            episode.orientation = orientation
            episode.access_type = EpisodeAccessType.FREE
            episode.coin_price = 0
            episode.premium = False
            episode.published_at = now
            episode.status = ContentStatus.PUBLISHED
            episode.sort_order = episode_number
            episode.deleted_at = None

    await db.commit()
    return len(SERIES)


async def run(action: str) -> None:
    async with SessionFactory() as db:
        if action == "sync":
            if get_settings().DEMO_CATALOG_ENABLED:
                count = await sync_demo_catalog(db)
                print(f"Drovixa showcase catalog ready: {count} series, {count * 2} episodes.")
            else:
                count = await remove_demo_catalog(db)
                await db.commit()
                print(f"Drovixa showcase catalog disabled: {count} series removed.")
        elif action == "install":
            count = await sync_demo_catalog(db)
            print(f"Drovixa showcase catalog installed: {count} series, {count * 2} episodes.")
        else:
            count = await remove_demo_catalog(db)
            await db.commit()
            print(f"Drovixa showcase catalog removed: {count} series.")
    await dispose_database()


def main() -> None:
    parser = argparse.ArgumentParser(description="Install or remove the Drovixa showcase catalog.")
    parser.add_argument("action", choices=("sync", "install", "remove"), nargs="?", default="sync")
    args = parser.parse_args()
    asyncio.run(run(args.action))


if __name__ == "__main__":
    main()
