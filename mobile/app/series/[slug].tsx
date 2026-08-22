import { useLocalSearchParams } from 'expo-router';
import { ContentDetailScreen } from '@/features/catalog/ContentDetailScreen';
export default function SeriesDetail(){const{slug}=useLocalSearchParams<{slug:string}>();return <ContentDetailScreen type="series" slug={slug}/>}
